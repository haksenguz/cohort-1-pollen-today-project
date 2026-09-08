"""LangGraph symptom agent (documentation §3, §7, §13).

ADR 0001 draws a hard line: the LLM converses and extracts structured data,
nothing more. Every node in this graph either (a) talks to the model to move
the conversation forward and pull fields out of it, or (b) is the plain,
deterministic `triage_node`, which is the *only* node allowed to call
`app.services.triage.assess` and therefore the only place a LOW / MODERATE /
EMERGENCY level is ever produced. No node here computes a level itself, and
no LLM output is ever written into `triage_level` — that field is only ever
set from a `TriageOutcome` returned by the rule engine.

Malformed or missing model output never crashes the graph and never invents a
fact: a field that can't be parsed is simply left unset, the turn is counted
against a hard `MAX_QUESTIONS` cap, and a previously-confirmed safety flag
(`breathing_difficulty` / `airway_swelling`) can never be flipped back to
False by a later, possibly-garbled extraction.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from typing import Protocol, TypedDict

from langgraph.graph import END, StateGraph

from app.services import triage

logger = logging.getLogger(__name__)

# Safety net: stop asking and hand off to the rule engine with whatever we
# have rather than looping forever on a confused model or a silent user.
MAX_QUESTIONS = 4

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

    assistant_reply: str | None

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
    """

    def complete(self, messages: Sequence[ChatMessage]) -> str: ...


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
        assistant_reply=None,
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


def _route_after_extract(state: AllergyState) -> str:
    """Never let the model's self-reported `ready` flag alone decide it is
    time to hand off to the rule engine. A malformed extraction can still
    parse a bare `"ready": true` while every substantive field (symptoms,
    severity, the two safety flags) fails validation and is dropped — trusting
    `ready` there would rush an under-informed conversation into a triage
    call built entirely from defaults. Only the deterministic completeness
    check, or exhausting the question budget, may route to `triage`.
    """
    if state.get("turn_count", 0) >= MAX_QUESTIONS:
        return "triage"
    if _has_enough_for_triage(state):
        return "triage"
    return "ask_question"


def make_extract_node(llm: LLMClient) -> Callable[[AllergyState], AllergyState]:
    def _extract(state: AllergyState) -> AllergyState:
        prompt: list[ChatMessage] = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            *state.get("messages", []),
        ]
        try:
            raw = llm.complete(prompt)
        except Exception:
            logger.warning("symptom_agent: extraction call to LLM failed", exc_info=True)
            state["extraction_error"] = True
            return state

        data = _safe_json_loads(raw)
        state["extraction_error"] = not data
        if data:
            merge_extraction(state, data)
        return state

    return _extract


def make_ask_question_node(llm: LLMClient) -> Callable[[AllergyState], AllergyState]:
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
            try:
                question = (llm.complete(prompt) or "").strip()
            except Exception:
                logger.warning("symptom_agent: question call to LLM failed", exc_info=True)
                question = ""
            if not question:
                question = FALLBACK_QUESTION

        state["assistant_reply"] = question
        state["messages"] = [*state.get("messages", []), {"role": "assistant", "content": question}]
        return state

    return _ask_question


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


def build_graph(llm: LLMClient):
    graph = StateGraph(AllergyState)
    graph.add_node("extract", make_extract_node(llm))
    graph.add_node("ask_question", make_ask_question_node(llm))
    graph.add_node("triage", triage_node)

    graph.set_entry_point("extract")
    graph.add_conditional_edges(
        "extract",
        _route_after_extract,
        {"ask_question": "ask_question", "triage": "triage"},
    )
    graph.add_edge("ask_question", END)
    graph.add_edge("triage", END)
    return graph.compile()


def run_turn(llm: LLMClient, state: AllergyState, user_message: str) -> AllergyState:
    """Append the user's message and run one pass of the graph: either a
    follow-up question comes back, or a rule-engine triage result does.
    """
    next_state: AllergyState = dict(state)  # type: ignore[assignment]
    next_state["messages"] = [
        *next_state.get("messages", []),
        {"role": "user", "content": user_message},
    ]
    graph = build_graph(llm)
    return graph.invoke(next_state)


class OpenAIChatClient:
    """Thin wrapper around the OpenAI SDK satisfying `LLMClient`."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=0,
        )
        return response.choices[0].message.content or ""


def get_llm_client(api_key: str, model: str = "gpt-4o-mini") -> LLMClient:
    if not api_key:
        raise RuntimeError(
            "openai_api_key is not configured; set it in backend/.env before using the chat agent"
        )
    return OpenAIChatClient(api_key=api_key, model=model)
