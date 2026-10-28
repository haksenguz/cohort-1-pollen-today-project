"""LangGraph symptom agent (documentation §3, §7, §13).

ADR 0001 draws a hard line: the LLM converses and extracts structured data,
nothing more. Every node in this graph either (a) talks to the model to move
the conversation forward and pull fields out of it, (b) offers the model a set
of read-only lookup tools and records what they returned, or (c) is the plain,
deterministic `triage_node`, which is the *only* node allowed to call
`app.services.triage.assess` and therefore the only place a LOW / MODERATE /
EMERGENCY level is ever produced. No node here computes a level itself, and
no LLM output — nor any tool result — is ever written into `triage_level`:
that field is only ever set from a `TriageOutcome` returned by the rule engine.
`tests/test_tool_registry.py` is the standing guard that makes that true of the
tool registry, not just of the nodes.

Tool calling is opt-in and off by default: with no registry passed in, this
graph is exactly the extract -> ask -> triage graph it has always been.

Malformed or missing model output never crashes the graph and never invents a
fact: a field that can't be parsed is simply left unset, the turn is counted
against a hard `MAX_QUESTIONS` cap, and a previously-confirmed safety flag
(`breathing_difficulty` / `airway_swelling`) can never be flipped back to
False by a later, possibly-garbled extraction.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.core.openai_client import (
    LLMCallError,
    ToolCall,
    ToolSpec,
    function_tool_spec,
)
from app.services import triage

logger = logging.getLogger(__name__)

# A lookup that hangs is a turn that never ends. Short on purpose: the clinic
# list is a convenience on a safety path, not the reason the user came.
NAVER_TIMEOUT_S = 5.0

# Safety net: stop asking and hand off to the rule engine with whatever we
# have rather than looping forever on a confused model or a silent user.
MAX_QUESTIONS = 4

# Hard ceiling on the reason -> act -> observe loop. Each step is one model call
# that may or may not request a tool, so a turn costs at most MAX_TOOL_STEPS
# extra calls and the loop always terminates, whether the model keeps asking for
# tools or not. This is the only thing standing between "tool calling" and an
# unbounded spend, so it is a module constant, not a tunable.
MAX_TOOL_STEPS = 3

SAFETY_QUESTION = (
    "Are you having any difficulty breathing, or swelling of your lips, tongue, or throat?"
)

FALLBACK_QUESTION = "Can you tell me more about your symptoms?"

EXTRACTION_SYSTEM_PROMPT = """You are the symptom-intake assistant for an allergy companion app.
Read the conversation so far and extract what the user has told you. You never diagnose, never
recommend medication, and never state how urgent or serious anything is — a separate rule-based
system decides that from the fields you extract.

Reply with ONLY a single JSON object, no prose, no markdown fences, with these keys:
  "symptoms": list of short snake_case strings (e.g. "itchy_eyes", "sneezing"), or [] if none yet
  "severity": integer 0-10 describing how bad the symptoms are overall, or null if unknown
  "duration": short string for when symptoms started (e.g. "this morning"), or null if unknown
  "possible_trigger": short string guess at the trigger (e.g. "pollen"), or null if unknown
  "breathing_difficulty": true/false if the user has clearly answered this, otherwise null
  "airway_swelling": true/false if the user has clearly answered this, otherwise null
  "ready": true once you have symptoms, a severity estimate, and both safety answers; else false

Only set a field from what the user actually said. Do not guess a safety answer that was never
asked or answered."""

QUESTION_SYSTEM_PROMPT = """You are the symptom-intake assistant for an allergy companion app.
Ask exactly ONE short, plain-language follow-up question to learn more about the user's symptoms,
their severity, duration, or likely trigger. Do not diagnose, do not suggest treatment, do not say
how serious or urgent anything is. Reply with the question only, no extra text."""

TOOL_SYSTEM_PROMPT = """You are the symptom-intake assistant for an allergy companion app.

You may look things up with the read-only tools offered to you before you answer. Lookups only
return factual directory data; they never judge the user's condition, and a tool that cannot be
reached says so plainly — say that to the user instead of guessing.

You never diagnose, never recommend medication, and never state how urgent or serious anything is.
A separate rule-based system owns that decision. Reply with the answer only, no extra text."""

_OBSERVE_PROMPT = "Use the lookup results above if they help, then answer the user in one line."


class ChatMessage(TypedDict):
    role: str  # "user" | "assistant"
    content: str


class AllergyState(TypedDict, total=False):
    """Conversation + extraction state (documentation §13), extended with the
    bookkeeping this graph needs to run a multi-turn loop."""

    messages: list[ChatMessage]

    symptoms: list[str]
    severity: int | None
    duration: str | None
    breathing_difficulty: bool | None
    airway_swelling: bool | None
    possible_trigger: str | None

    turn_count: int
    ready: bool
    extraction_error: bool

    # Tool-loop bookkeeping, written only by `make_tool_node`. `tool_observations`
    # holds what the tools actually returned, verbatim. Neither field is ever
    # merged into the extraction fields below, and neither can reach a triage
    # verdict: the node has no path to write `triage_level` or `triage_reasons`.
    tool_steps: int
    tool_observations: list[str]

    # J4: the `kind` of the last model-call failure ("timeout", "rate_limit",
    # "unavailable", "malformed"), or None. Set only from an `LLMCallError` —
    # never from a guess. `app.api.chat` reads it to tell the user their
    # message could not be processed, instead of silently asking another
    # question forever. A `None` here with `extraction_error` True means the
    # model answered but not with parseable JSON, which is a normal, quiet
    # degradation.
    llm_error_kind: str | None

    assistant_reply: str | None

    # True when the reply was handed over by a streaming client, piece by
    # piece, as the model wrote it. The caller uses it to know that the text is
    # already on the wire and must not be sent a second time.
    reply_from_stream: bool

    # Set only by triage_node, only from a TriageOutcome. Never by the LLM.
    triage_level: str | None
    triage_recommendation: str | None
    triage_reasons: list[str]
    triage_rule_version: str | None


class LLMClient(Protocol):
    """The only boundary the graph has with a model.

    A real implementation talks to OpenAI; tests supply a scripted fake. The
    graph's control flow, and in particular which node gets to decide safety,
    never depends on which implementation is wired in.

    `complete` is the entire required contract. Tool calling is a separate,
    optional capability (`ToolCallingLLMClient.complete_with_tools` in
    `app.core.openai_client`); the tool node duck-types for it and is skipped
    entirely when a client does not offer it, so every existing fake is still
    a valid `LLMClient`.
    """

    def complete(self, messages: Sequence[ChatMessage]) -> str: ...


class ToolNotWiredError(RuntimeError):
    """A registered tool has no real executor behind it yet.

    Raised instead of returning a placeholder payload. A lookup tool that
    invents a plausible-looking result is worse than no tool at all: the model
    would quote fabricated places or numbers to the user as if they came from
    the provider.
    """


@dataclass(frozen=True)
class ToolDefinition:
    """One named read-only tool.

    `parameters` is the JSON Schema handed to the model, `result_schema` is the
    shape this tool promises to return. Both are walked by
    `tests/test_tool_registry.py`, which enforces the ADR 0001 boundary: no
    tool may take a safety field as input or hand one back.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    result_schema: dict[str, Any]
    execute: Callable[[Mapping[str, Any]], Any]
    wired: bool = True

    def as_provider_spec(self) -> ToolSpec:
        return function_tool_spec(self.name, self.description, self.parameters)


class ToolRegistry:
    """A named collection of tool definitions.

    Deliberately dumb: it stores what it is given and hands it back. Every
    policy question about *which* tools may exist (no urgency assessment, no
    writes, no safety field in or out) is enforced by the guard test in
    `tests/test_tool_registry.py`, not by clever registration logic here — a
    registry that silently refused a bad tool would leave the boundary
    untested, and an untested boundary is not a boundary.
    """

    def __init__(self, tools: Sequence[ToolDefinition] = ()) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> ToolDefinition:
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def __len__(self) -> int:
        return len(self._tools)

    def provider_specs(self) -> list[ToolSpec]:
        return [tool.as_provider_spec() for tool in self._tools.values()]


# Read-only lookup: reuses what `GET /api/hospitals/nearby` already does —
# Naver Local Search, ranked by haversine distance. Naver takes a keyword, not a
# radius, so `radius_m` stays a client-side filter and `location_query` biases
# the keyword toward the caller's area.


@dataclass(frozen=True)
class NearbyCareOrigin:
    """Where "nearby" means, resolved by the server and never by the model.

    The model's only route to a location is the stored profile, which it cannot
    read. Asking it for `latitude`/`longitude` made the tool unsatisfiable: the
    turn ran `starting -> extracting -> saving -> done` with no call at all,
    because there was no honest way for the model to produce the required
    arguments. Resolving the origin here is what makes the tool reachable.
    """

    latitude: float
    longitude: float
    location_query: str | None = None


@dataclass(frozen=True)
class NearbyCareSearch:
    """Rows a lookup produced, plus whether the provider was reachable at all.

    `provider_available=False` means the search never ran. That is a different
    fact from "we searched and there is nothing nearby", and a client that
    cannot tell them apart will eventually tell a user with a clinic around the
    corner that there is nothing nearby.
    """

    clinics: list[dict[str, Any]]
    provider_available: bool


# Codes a wired tool can refuse with. The vocabulary is deliberately tiny and is
# the same one `app.api.chat` publishes as `ToolCallEvent.code`, so a refusal
# names why the user should do something different next time.
NO_LOCATION = "no_location"
PROVIDER_UNAVAILABLE = "provider_unavailable"

# What a client is shown for each refusal. Plain English, no identifiers, and no
# claim about the user's health: "we could not search" is not "there is nothing".
TOOL_REFUSAL_MESSAGES = {
    NO_LOCATION: (
        "We need your location first. Your profile has no location saved, so we "
        "could not search. This does not mean there are no clinics around you."
    ),
    PROVIDER_UNAVAILABLE: (
        "Clinic search is offline. The clinic provider is not connected, so we "
        "could not search. We did not search."
    ),
}


class ToolRefused(Exception):
    """A wired tool that cannot answer right now, and why.

    Not a crash and not an absence of data: the tool exists, the model asked it
    a fair question, and the answer is "not with the information we have". The
    `code` is what survives to the wire so the client can offer the fix instead
    of rendering a dead end.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _nearby_care_search(
    origin: NearbyCareOrigin,
    *,
    specialty: str | None,
    location_query: str | None,
) -> NearbyCareSearch:
    """Call the async hospital service from this synchronous executor.

    The turn runs on a worker thread via `asyncio.to_thread`, and the request's
    pooled `httpx.AsyncClient` is bound to the event loop serving the request —
    using it from a second loop fails at the first await. So this opens its own
    client on its own loop and closes it again. One extra connection per lookup
    is the price of not having a client owned by a loop that is not running.
    """
    from app.core.config import get_settings  # noqa: PLC0415 — avoids an import cycle
    from app.services.hospital_service import (  # noqa: PLC0415 — same
        NaverLocalClient,
        find_nearby_hospitals,
    )

    async def _run() -> NearbyCareSearch:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=NAVER_TIMEOUT_S) as http:
            outcome = await find_nearby_hospitals(
                NaverLocalClient(http, settings.naver_client_id, settings.naver_client_secret),
                latitude=origin.latitude,
                longitude=origin.longitude,
                specialty=specialty,
                location_query=location_query or origin.location_query,
            )
        return NearbyCareSearch(
            clinics=[
                {
                    "name": r.name,
                    "address": r.address,
                    "distance_m": r.distance_m,
                    "phone": r.phone,
                    "rank": r.rank,
                }
                for r in outcome.results
            ],
            provider_available=outcome.provider_available,
        )

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — a lookup must not break the turn
        logger.warning("nearby care search failed (%s)", exc)
        raise ToolRefused(PROVIDER_UNAVAILABLE) from exc


def build_nearby_care_tool(
    origin: NearbyCareOrigin | None,
    *,
    search: Callable[..., NearbyCareSearch] | None = None,
) -> ToolDefinition:
    """The clinic lookup, wired to `origin`, or refusing for want of one.

    `search` is the seam: tests hand in a fake and never touch the network.
    `origin=None` still produces a *wired* tool. An unwired one would degrade
    to "that lookup is not available right now", which is a claim about the
    product when the truth is about the user — and the one thing a user on a
    safety path can act on in five seconds would be lost.
    """
    lookup = search or _nearby_care_search

    def _execute(arguments: Mapping[str, Any]) -> Any:
        if origin is None:
            raise ToolRefused(NO_LOCATION)
        specialty = arguments.get("speciality")
        outcome = lookup(
            origin,
            specialty=str(specialty) if specialty else None,
            location_query=arguments.get("location_query") or None,
        )
        if not outcome.provider_available:
            raise ToolRefused(PROVIDER_UNAVAILABLE)
        return {
            "clinics": outcome.clinics,
            "provider_available": outcome.provider_available,
        }

    return ToolDefinition(
        name=FIND_NEARBY_CARE_TOOL,
        description=(
            "Look up nearby medical facilities for the user's saved location, "
            "optionally filtered by speciality. Read-only: it looks places up "
            "and changes nothing. The location comes from the user's profile, "
            "so you do not need to supply coordinates."
        ),
        parameters={
            "type": "object",
            "properties": {
                "speciality": {
                    "type": "string",
                    "description": "Optional speciality label, e.g. ENT, ALLERGY, GENERAL.",
                },
                "location_query": {
                    "type": "string",
                    "description": (
                        "Optional place or district name to narrow the search, e.g. a city. "
                        "Only needed when the user names somewhere other than their saved "
                        "location."
                    ),
                },
            },
            "required": [],
        },
        result_schema={
            "type": "object",
            "properties": {
                "clinics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "address": {"type": ["string", "null"]},
                            "distance_m": {"type": ["integer", "null"]},
                            "phone": {"type": ["string", "null"]},
                            "rank": {"type": "integer"},
                        },
                    },
                },
                "provider_available": {"type": "boolean"},
            },
        },
        execute=_execute,
    )


FIND_NEARBY_CARE_TOOL = "find_nearby_hospitals"

# Kept as a module attribute so the guard test and any other caller can reach the
# shipped definition without building a registry around it.
FIND_NEARBY_HOSPITALS = build_nearby_care_tool(None)


def default_tool_registry(origin: NearbyCareOrigin | None = None) -> ToolRegistry:
    """The registry the app ships with: read-only lookups only.

    `origin` is the caller's saved location. It is resolved per request by
    `app.api.chat`, never asked of the model.
    """
    return ToolRegistry([build_nearby_care_tool(origin)])


# Reports what the agent is doing, stage by stage, so `app.api.chat` can tell
# the user the turn is alive. A turn is two sequential model calls plus the
# rule engine — several seconds with nothing on screen otherwise, which reads
# as "broken" rather than "working".
#
# These are progress labels, NOT tool calls: a stage describes an internal
# step of a model call, so it must never be phrased as if the model were
# invoking something. The tool node emits no stage of its own for the same
# reason — a "calling_tool" label would read as the model acting on the app,
# which is precisely the boundary `tests/test_tool_registry.py` guards.
ProgressCallback = Callable[[str], None]


def initial_state(history: Sequence[ChatMessage] | None = None) -> AllergyState:
    """A fresh state, optionally seeded with prior turns loaded from storage."""
    return AllergyState(
        messages=list(history or []),
        symptoms=[],
        severity=None,
        duration=None,
        breathing_difficulty=None,
        airway_swelling=None,
        possible_trigger=None,
        turn_count=0,
        ready=False,
        extraction_error=False,
        tool_steps=0,
        tool_observations=[],
        llm_error_kind=None,
        assistant_reply=None,
        reply_from_stream=False,
        triage_level=None,
        triage_recommendation=None,
        triage_reasons=[],
        triage_rule_version=None,
    )


def _safe_json_loads(text: str) -> dict:
    """Best-effort parse of model output. Never raises; returns {} on any
    malformed, empty, or non-JSON response."""
    if not isinstance(text, str):
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        first_line, _, rest = stripped.partition("\n")
        stripped = rest if first_line.lower().strip() in ("json", "") else stripped
    try:
        start = stripped.index("{")
        end = stripped.rindex("}") + 1
    except ValueError:
        return {}
    try:
        data = json.loads(stripped[start:end])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _clean_symptom(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower().replace(" ", "_")
    return cleaned or None


def merge_extraction(state: AllergyState, data: dict) -> None:
    """Merge parsed extraction fields into state in place.

    Unknown, missing, or malformed fields are left untouched rather than
    guessed. A field the model *did* return but that fails validation (wrong
    type, out-of-range severity, garbage symptom entries) is dropped, not
    coerced, so a malformed response degrades to "no new information" instead
    of polluting state with something invented.
    """
    if isinstance(data.get("symptoms"), list):
        cleaned = [_clean_symptom(s) for s in data["symptoms"]]
        cleaned = [s for s in cleaned if s]
        if cleaned:
            merged = dict.fromkeys(state.get("symptoms") or [])
            merged.update(dict.fromkeys(cleaned))
            state["symptoms"] = list(merged)

    severity = data.get("severity")
    if isinstance(severity, int) and not isinstance(severity, bool) and 0 <= severity <= 10:
        state["severity"] = severity

    duration = data.get("duration")
    if isinstance(duration, str) and duration.strip():
        state["duration"] = duration.strip()

    trigger = data.get("possible_trigger")
    if isinstance(trigger, str) and trigger.strip():
        state["possible_trigger"] = trigger.strip()

    # Safety flags: accept only explicit booleans. Once confirmed true, a
    # later turn can never silently flip it back to false — that would need
    # an explicit human correction path, not a re-extraction.
    for key in ("breathing_difficulty", "airway_swelling"):
        value = data.get(key)
        if isinstance(value, bool):
            if state.get(key) is True and value is False:
                continue
            state[key] = value

    ready = data.get("ready")
    if isinstance(ready, bool):
        state["ready"] = ready


def _has_enough_for_triage(state: AllergyState) -> bool:
    if state.get("breathing_difficulty") is None or state.get("airway_swelling") is None:
        return False
    if not state.get("symptoms"):
        return False
    return state.get("severity") is not None


def _has_confirmed_red_flag(state: AllergyState) -> bool:
    """A safety flag the user has affirmatively reported as True.

    This is a *routing* shortcut, not a safety decision. The level itself is
    still produced only by `triage_node` calling the rule engine, so ADR 0001
    holds: the LLM never chooses a level, this only decides to stop asking.
    """
    return state.get("breathing_difficulty") is True or state.get("airway_swelling") is True


def _route_after_extract(state: AllergyState) -> str:
    """Never let the model's self-reported `ready` flag alone decide it is
    time to hand off to the rule engine. A malformed extraction can still
    parse a bare `"ready": true` while every substantive field (symptoms,
    severity, the two safety flags) fails validation and is dropped — trusting
    `ready` there would rush an under-informed conversation into a triage
    call built entirely from defaults. Only the deterministic completeness
    check, a confirmed red flag, or exhausting the question budget may route
    to `triage`.
    """
    if state.get("turn_count", 0) >= MAX_QUESTIONS:
        return "triage"
    # A confirmed red flag short-circuits the rest of the intake. The live J3
    # eval showed the failure this prevents: for "숨쉬기 힘들고 목이 부어서
    # 부풀었어요" (hard to breathe, throat swollen) the model sets both safety
    # flags but returns no severity, so the completeness check below said
    # "keep asking" and the app replied "when did these symptoms start?" to a
    # user who had just said they could not breathe. There is nothing left to
    # learn that changes the answer — the rule engine returns EMERGENCY for
    # this input regardless — so the only cost of asking is delay.
    if _has_confirmed_red_flag(state):
        return "triage"
    if _has_enough_for_triage(state):
        return "triage"
    return "ask_question"


def make_extract_node(
    llm: LLMClient, progress: ProgressCallback | None = None
) -> Callable[[AllergyState], AllergyState]:
    def _extract(state: AllergyState) -> AllergyState:
        prompt: list[ChatMessage] = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            *state.get("messages", []),
        ]
        if progress is not None:
            progress("extracting")
        try:
            raw = llm.complete(prompt)
        except LLMCallError as exc:
            # J4: the single client boundary normalizes every provider failure
            # into an LLMCallError with a `kind`. A timeout or rate limit is a
            # degraded turn, not a crash: we set extraction_error and return
            # state unchanged so the router keeps asking / eventually hands off
            # to the rule engine with whatever we have.
            logger.warning("symptom_agent: extraction call failed (%s)", exc.kind)
            state["extraction_error"] = True
            state["llm_error_kind"] = exc.kind
            return state
        except Exception:
            # Defensive: a non-OpenAI client (or an unexpected SDK error) must
            # still degrade rather than 500 the stream.
            logger.warning("symptom_agent: extraction call to LLM failed", exc_info=True)
            state["extraction_error"] = True
            state["llm_error_kind"] = "unavailable"
            return state

        data = _safe_json_loads(raw)
        state["extraction_error"] = not data
        if data:
            merge_extraction(state, data)
        return state

    return _extract


def make_ask_question_node(
    llm: LLMClient, progress: ProgressCallback | None = None
) -> Callable[[AllergyState], AllergyState]:
    def _ask_question(state: AllergyState) -> AllergyState:
        state["turn_count"] = state.get("turn_count", 0) + 1

        missing_safety = (
            state.get("breathing_difficulty") is None or state.get("airway_swelling") is None
        )
        if missing_safety:
            question = SAFETY_QUESTION
        else:
            prompt: list[ChatMessage] = [
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                *state.get("messages", []),
            ]
            if progress is not None:
                progress("asking")
            question = _ask_the_model(llm, prompt, state)
            if not question:
                question = FALLBACK_QUESTION

        state["assistant_reply"] = question
        state["messages"] = [*state.get("messages", []), {"role": "assistant", "content": question}]
        return state

    return _ask_question


def _ask_the_model(llm: LLMClient, prompt: list[ChatMessage], state: AllergyState) -> str:
    """The model's own follow-up question, streamed when the client can stream.

    A client that offers `stream_complete` hands the question over in pieces
    as the model writes it, so the caller can show the first words long before
    the last one. A client without that capability gets the whole answer in
    one call, which is what every offline fake does.

    The pieces are used exactly as they arrive. Trimming them would break the
    promise the client relies on: what it appended is what the reply is.
    """
    streamer = getattr(llm, "stream_complete", None)
    if callable(streamer):
        pieces: list[str] = []
        try:
            for piece in streamer(prompt):
                if not piece.strip():
                    continue
                pieces.append(piece)
        except LLMCallError as exc:
            logger.warning("symptom_agent: streamed question failed (%s)", exc.kind)
            state["llm_error_kind"] = exc.kind
            return ""
        except Exception:
            logger.warning("symptom_agent: streamed question failed", exc_info=True)
            state["llm_error_kind"] = "unavailable"
            return ""
        if not pieces:
            return ""
        state["reply_from_stream"] = True
        return "".join(pieces)

    try:
        return (llm.complete(prompt) or "").strip()
    except LLMCallError as exc:
        logger.warning("symptom_agent: question call failed (%s)", exc.kind)
        state["llm_error_kind"] = exc.kind
        return ""
    except Exception:
        logger.warning("symptom_agent: question call to LLM failed", exc_info=True)
        state["llm_error_kind"] = "unavailable"
        return ""


def _observe(registry: ToolRegistry, call: ToolCall) -> str:
    """Run one tool and render its outcome as a string for the model.

    Never raises. An unknown name, an unwired executor, a malformed argument
    body, or an executor blowing up all come back as a short sentence the model
    can read and pass on — a tool problem is never allowed to take down a turn,
    and least of all an emergency one.

    The return value is deliberately a *string*. Whatever a tool returns is
    observed text, never state: there is no code path from here to
    `triage_level`, `triage_reasons`, or any extracted field, which is exactly
    what the ADR 0001 guard test pins down.
    """
    tool = registry.get(call.name)
    if tool is None:
        logger.warning("symptom_agent: model asked for unknown tool %r", call.name)
        return "error: that lookup is not available."
    if not tool.wired:
        return "error: that lookup is not available right now."
    try:
        result = tool.execute(call.arguments)
    except ToolRefused as exc:
        logger.info("symptom_agent: %s declined (%s)", tool.name, exc.code)
        # The code is machine-readable and the sentence is for the model; both
        # ride one observation because `tool_observations` is a list of strings
        # and adding a parallel list would put the two out of step the moment a
        # call produced more than one observation.
        #
        # `error: ` stays at the front on purpose. It is the prefix
        # `app.api.chat._settle` reads to decide a call failed, and a refusal
        # that missed it would fall through to `json.loads`, fail to parse, and
        # be reported to the user as a successful lookup.
        return f"error: {exc.code}: {TOOL_REFUSAL_MESSAGES[exc.code]}"
    except ToolNotWiredError:
        return "error: that lookup is not available right now."
    except Exception as exc:  # noqa: BLE001 — a tool must not break the turn
        logger.warning("symptom_agent: tool %s failed (%s)", tool.name, exc)
        return "error: that lookup failed."
    return json.dumps(result, ensure_ascii=False, default=str)


def make_tool_node(
    llm: LLMClient,
    registry: ToolRegistry | None,
) -> Callable[[AllergyState], AllergyState]:
    """reason -> act -> observe, hard-bounded at MAX_TOOL_STEPS.

    Skipped entirely when there is no registry, or when the client offers no
    `complete_with_tools` — a plain `complete(messages)` client keeps working
    unchanged, which is what every existing fake does.

    Emits no progress stage on purpose. The stage vocabulary rendered by
    `app.api.chat` describes internal steps of a model call, and a stage that
    reads like "calling a tool" would be a lie about the boundary; the node is
    fast and bounded, and the observations land in state where they can be
    logged or asserted.
    """

    def _tools(state: AllergyState) -> AllergyState:
        if registry is None or not registry.definitions():
            return state
        if not hasattr(llm, "complete_with_tools"):
            return state

        specs = registry.provider_specs()
        transcript: list[dict[str, Any]] = [
            {"role": "system", "content": TOOL_SYSTEM_PROMPT},
            *state.get("messages", []),
        ]
        observations: list[str] = []
        steps = 0

        for _ in range(MAX_TOOL_STEPS):
            steps += 1
            if steps > 1 and observations:
                # Only re-offer tools once there is something new to observe;
                # a model that has just seen a result answers instead of
                # re-asking, which is what keeps the loop short in practice.
                transcript = [*transcript, {"role": "user", "content": _OBSERVE_PROMPT}]
            try:
                turn = llm.complete_with_tools(transcript, specs)  # type: ignore[attr-defined]
            except LLMCallError as exc:
                logger.warning("symptom_agent: tool-enabled call failed (%s)", exc.kind)
                break
            except Exception:
                logger.warning("symptom_agent: tool-enabled call failed", exc_info=True)
                break

            if not turn.tool_calls:
                break

            for call in turn.tool_calls:
                observation = _observe(registry, call)
                observations.append(observation)
                transcript = [
                    *transcript,
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": observation,
                    },
                ]

        state["tool_steps"] = steps
        state["tool_observations"] = observations
        return state

    return _tools


def triage_node(state: AllergyState) -> AllergyState:
    """The only node that decides urgency, and it does so by calling the
    deterministic rule engine — never the LLM. Unresolved safety flags (the
    conversation hit MAX_QUESTIONS without an answer) default to False here,
    same as an unauthenticated API caller would default them; they never
    default to True, since inventing a positive safety flag is exactly the
    kind of fabrication ADR 0001 and CLAUDE.md forbid.
    """
    breathing_difficulty = bool(state.get("breathing_difficulty"))
    airway_swelling = bool(state.get("airway_swelling"))
    outcome = triage.assess(
        triage.SymptomInput(
            symptoms=state.get("symptoms") or [],
            severity=state.get("severity"),
            breathing_difficulty=breathing_difficulty,
            airway_swelling=airway_swelling,
        )
    )

    # Record the exact values the rule engine used, including a defaulted
    # False for a flag the conversation never got an explicit answer to, so
    # state and persistence never carry an ambiguous None behind a decision
    # that has already been made.
    state["breathing_difficulty"] = breathing_difficulty
    state["airway_swelling"] = airway_swelling
    state["triage_level"] = outcome.level.value
    state["triage_recommendation"] = outcome.recommendation
    state["triage_reasons"] = outcome.reasons
    state["triage_rule_version"] = outcome.rule_version
    state["assistant_reply"] = outcome.recommendation
    state["messages"] = [
        *state.get("messages", []),
        {"role": "assistant", "content": outcome.recommendation},
    ]
    return state


def make_triage_node(
    progress: ProgressCallback | None = None,
) -> Callable[[AllergyState], AllergyState]:
    """`triage_node` with a progress hook.

    The stage is labelled as the safety rules running, not the model deciding —
    that distinction is the whole point of ADR 0001, and it is worth putting in
    front of the user at the exact moment the verdict is being produced.
    """

    def _triage(state: AllergyState) -> AllergyState:
        if progress is not None:
            progress("assessing")
        return triage_node(state)

    return _triage


def build_graph(
    llm: LLMClient,
    progress: ProgressCallback | None = None,
    registry: ToolRegistry | None = None,
):
    """Compile the graph.

    With no `registry` — the default, and what every production call site and
    every existing test uses — this is exactly the graph it was before tools
    existed: extract -> (ask_question | triage), two model calls at most. The
    tool node is added to the front of the graph only when a caller explicitly
    opts in, so offering tools can never change how a turn that uses none
    behaves.
    """
    graph = StateGraph(AllergyState)
    graph.add_node("extract", make_extract_node(llm, progress))
    graph.add_node("ask_question", make_ask_question_node(llm, progress))
    graph.add_node("triage", make_triage_node(progress))

    if registry is not None and registry.definitions():
        graph.add_node("tools", make_tool_node(llm, registry))
        graph.set_entry_point("tools")
        graph.add_edge("tools", "extract")
    else:
        graph.set_entry_point("extract")

    graph.add_conditional_edges(
        "extract",
        _route_after_extract,
        {"ask_question": "ask_question", "triage": "triage"},
    )
    graph.add_edge("ask_question", END)
    graph.add_edge("triage", END)
    return graph.compile()


def run_turn(
    llm: LLMClient,
    state: AllergyState,
    user_message: str,
    progress: ProgressCallback | None = None,
    registry: ToolRegistry | None = None,
) -> AllergyState:
    """Append the user's message and run one pass of the graph: either a
    follow-up question comes back, or a rule-engine triage result does.

    `registry` is optional and defaults to None, meaning no tools are offered
    and the pass costs exactly the two model calls it always did.

    A client that can stream hands the reply over piece by piece, and the
    caller sees each piece as it arrives. A client that cannot gets the whole
    answer in one call.
    """
    next_state: AllergyState = dict(state)  # type: ignore[assignment]
    next_state["messages"] = [
        *next_state.get("messages", []),
        {"role": "user", "content": user_message},
    ]
    graph = build_graph(llm, progress, registry)
    return graph.invoke(next_state)


# J7: the duplicate `OpenAIChatClient` and `get_llm_client` that used to live
# here are gone. There is now exactly one boundary with a model, in
# `app/core/openai_client.py`; it satisfies this module's structural
# `LLMClient` Protocol. `app.api.chat` builds the real client through
# `get_openai_client_from_settings()` and passes it in, so this module imports
# no concrete SDK and its tests keep running against a scripted fake.
