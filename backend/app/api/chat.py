"""Chat endpoint for the symptom agent (documentation §12, ADR 0002).

The frontend PWA streams chat over SSE (ADR 0002), so this endpoint responds
with `text/event-stream`: several `message` events carrying incremental
fragments of the assistant reply, and a `done` event carrying the complete
authoritative reply plus the same fields as documentation §12's example
response, the structured extraction and, once the rule engine has run, its
triage verdict. A `tool` event reports each lookup the agent makes while the
turn is still running, and `done` repeats them as an audit trail so a client
that missed a live frame can still show what ran.

The split is additive, never corrective: a client appends each `delta` and
then reconciles against `done`, which is always sufficient on its own to
render the turn.

Safety boundary (ADR 0001): this module never decides urgency itself. It
loads/saves conversation state and calls `app.agents.symptom_agent.run_turn`,
which only ever produces a `triage_level` by calling the deterministic
`app.services.triage.assess`. Nothing here inspects symptoms and picks a
level on its own.
"""

import asyncio
import json
import logging
import queue
import re
from collections.abc import AsyncIterator
from functools import partial
from typing import Annotated, Any, Literal
from weakref import WeakSet

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents import symptom_agent
from app.core.config import get_settings
from app.core.db import SessionDep
from app.core.enums import ConversationStatus, MessageRole
from app.core.rate_limit import get_limiter
from app.core.security import CurrentUser
from app.models import Conversation, Message, SymptomEvent, TriageResult, User
from app.services import escalation, triage

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: int | None = None


ToolStatus = Literal["running", "done", "error"]


class ToolCallEvent(BaseModel):
    """One tool call as the client sees it.

    `summary` is a single short plain-English line, never an exception and never
    JSON — the audience is a beginner, not a debugger. `args` is set on
    `running` only, where it is what the model asked for; once the call settles
    it is noise. `id` is what lets a client tie a live event to its audit row.

    Nothing in this shape can carry a safety field. ADR 0001 keeps every
    urgency decision in `app.services.triage`, and a tool event reports a
    lookup, it never judges the user.
    """

    id: str
    name: str
    status: ToolStatus
    summary: str | None = None
    args: dict[str, Any] | None = None
    # The tool's actual rows, so the user can read the answer instead of a
    # sentence about it. Present on `done` only, and only for a tool with an
    # agreed key in `_TOOL_RESULT_KEYS` - never on `running` or `error`, and
    # never with a key invented on the spot.
    result: dict[str, Any] | None = None
    # Why the call could not produce a result, in the agreed vocabulary. Without
    # it a missing location and a dead provider both arrive as `error` with a
    # sentence, and only one of them is something the user can fix in five
    # seconds. Absent on every success.
    code: str | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: int
    symptoms: list[str]
    severity: int | None
    duration: str | None
    possible_trigger: str | None
    breathing_difficulty: bool | None
    airway_swelling: bool | None
    triage_level: str | None
    triage_reasons: list[str]
    triage_rule_version: str | None
    tool_calls: list[ToolCallEvent] | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Words per `message` event. Small enough that a client repaints several times
# across one reply, large enough not to turn a short answer into dozens of SSE
# frames.
_FRAGMENT_WORDS = 6


def _fragments(text: str, *, words_per_fragment: int = _FRAGMENT_WORDS) -> list[str]:
    """Cut `text` into fragments that concatenate back to it exactly.

    The cut points are word-start offsets read off `text` itself, so every
    character lands in exactly one fragment: nothing is dropped, nothing is
    duplicated, and no whitespace is inserted at a boundary. A fragment may end
    mid-space-run only where the original already had one.

    An empty string yields no fragments. The `done` event still carries
    `message: ""`, which is everything a client needs to render the turn, so an
    empty delta would be pure noise. Whitespace-only text is *not* empty and is
    returned whole, because its whitespace is content the client must not lose.
    """
    if not text:
        return []

    cuts = [match.start() for match in re.finditer(r"\S+", text)][::words_per_fragment]
    parts: list[str] = []
    start = 0
    for cut in cuts[1:]:
        parts.append(text[start:cut])
        start = cut
    parts.append(text[start:])
    return parts


# ---------------------------------------------------------------------------
# Tool activity.
#
# The agent runs a bounded reason -> act -> observe loop inside `run_turn`, and
# the generator below is outside it, so tool activity has to cross that
# boundary the same way progress stages already do: something on the worker
# thread puts an event on a queue, this generator drains it.
#
# The two halves of a call are not available from the same place. A call's id,
# name and arguments exist only in the model's tool request, so they are read
# off the client by `_ToolActivityLLM` before `run_turn` gets to see them. What
# the call actually returned is recorded afterwards as one plain string per
# call, in the order the calls were made, which is enough to settle each one.
# ---------------------------------------------------------------------------

# The one prefix `symptom_agent._observe` puts on a call that failed. It never
# carries the exception behind it, so it is the whole of what may be shown.
_ERROR_PREFIX = "error: "


def _split_refusal(text: str) -> tuple[str | None, str]:
    """Peel a machine-readable refusal code off the front of a failure.

    `symptom_agent` writes a refusal as `error: <code>: <sentence>`. The code is
    only taken when it is one this build knows about, so a sentence that merely
    starts with a word and a colon is still shown whole rather than being
    silently cut in half.
    """
    head, separator, tail = text.partition(": ")
    if separator and head in symptom_agent.TOOL_REFUSAL_MESSAGES:
        return head, tail
    return None, text


# Anything shaped like an identifier - `find_nearby_hospitals`, `radius_m`,
# `KEY_ERROR`. These are code tokens and this text is read by a person.
_IDENTIFIER = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", re.IGNORECASE)


def _for_the_user(text: str, tool_name: str) -> str:
    """Turn one sentence the agent wrote into one line a beginner can read.

    The observation keeps the tool name on purpose: the model needs to know
    which lookup failed to decide what to do next. The user does not, and a
    snake_case identifier on a safety screen is the same class of leak as a
    raw exception - so it is stripped here, at the one place the sentence
    becomes user-facing, rather than at the source where the model would lose
    it.
    """
    if tool_name:
        text = re.sub(rf"\b{re.escape(tool_name)}\b", "that", text, flags=re.IGNORECASE)
    text = _IDENTIFIER.sub("", text)
    return " ".join(text.split()).replace("_", " ").strip()


def _as_a_line(sentence: str, tool_name: str = "") -> str:
    """One readable line out of one the agent already wrote for a human.

    Only tidied, never rewritten: a capital, a full stop, no identifiers. A
    lookup whose failure has no sentence at all says the one thing that is true.
    """
    text = _for_the_user(sentence, tool_name)
    if not text:
        return "That lookup did not finish."
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else f"{text}."


# The result key each tool's payload is published under. A tool the client has
# no agreed key for gets no payload rather than an invented one - the wire shape
# is a contract, and guessing a key is how a client ends up reading `undefined`.
_TOOL_RESULT_KEYS = {
    # The name the contract uses and the name currently registered are the same
    # lookup under two labels; both publish under the same key.
    "find_nearby_hospitals": "clinics",
    "find_nearby_care": "clinics",
}


def _settle(observation: str, tool_name: str) -> tuple[ToolStatus, str, dict | None, str | None]:
    """Read one settled observation as `(status, summary, result, code)`.

    A failed call comes back as a sentence saying what went wrong, and that
    sentence is the entire user-facing truth about it — there is no honest
    result to add, so none is invented and no payload is published. If the tool
    declined with a code, that code is carried alongside so the client can offer
    the fix instead of a dead end.

    A successful call comes back as the tool's own JSON. It is decoded far
    enough to count what arrived and, for a tool with an agreed result key, to
    hand the rows to the client so the user can actually see them. What any
    particular tool means by its result belongs to the tool, not to this layer.

    An empty observation means the call was announced but never came back. It
    is reported as unfinished rather than as a success, because nothing here
    saw a result and reporting one would be making it up.
    """
    if not observation.strip():
        return "error", _as_a_line("", tool_name), None, None
    if observation.startswith(_ERROR_PREFIX):
        code, sentence = _split_refusal(observation[len(_ERROR_PREFIX) :])
        return "error", _as_a_line(sentence, tool_name), None, code
    try:
        result = json.loads(observation)
    except json.JSONDecodeError:
        return "done", "Finished the lookup.", None, None

    key = _TOOL_RESULT_KEYS.get(tool_name)
    if isinstance(result, list):
        summary = "No results found." if not result else f"Found {len(result)} results."
        return "done", summary, ({key: result} if key else None), None
    if isinstance(result, dict) and key:
        # A tool that already returns the agreed key publishes as itself, so a
        # payload that carries more than rows - `provider_available` is what
        # separates "searched and found none" from "never searched" - is not
        # flattened down to a list and silently loses that distinction. Any
        # other dict is still published under the agreed key, which is the only
        # place a client knows to look.
        if key in result:
            rows = result[key]
            summary = (
                "No results found."
                if isinstance(rows, list) and not rows
                else f"Found {len(rows)} results."
                if isinstance(rows, list)
                else "Finished the lookup."
            )
            return "done", summary, result, None
        return "done", "Finished the lookup.", {key: result}, None
    return "done", "Finished the lookup.", None, None


def _drain(pending: queue.Queue[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Everything queued so far, oldest first, without blocking the event loop."""
    events: list[tuple[str, dict]] = []
    while True:
        try:
            events.append(pending.get_nowait())
        except queue.Empty:
            return events


class _ToolActivityLLM:
    """Announces every tool call the model asks for, before it is observed.

    `run_turn` runs the tool itself and reports only the outcome, so this is
    the one point inside the files this module owns where a call's id, name and
    arguments still exist. Wrapping rather than unwrapping the loop keeps the
    agent's control flow, its step cap and its observations exactly as they
    were; this only reads what passes by.
    """

    def __init__(self, inner: symptom_agent.LLMClient, announce) -> None:
        self._inner = inner
        self._announce = announce
        self._calls = 0

    def complete(self, messages) -> str:
        return self._inner.complete(messages)

    def complete_with_tools(self, messages, tools):
        turn = self._inner.complete_with_tools(messages, tools)
        for call in turn.tool_calls:
            self._calls += 1
            self._announce(
                ToolCallEvent(
                    # A provider that returns no id still has to be
                    # correlatable, so it gets one for this turn.
                    id=call.id or f"call_{self._calls}",
                    name=call.name,
                    status="running",
                    args=dict(call.arguments or {}),
                )
            )
        return turn


def _with_tool_activity(llm: symptom_agent.LLMClient, announce) -> symptom_agent.LLMClient:
    """Wrap `llm` so its tool calls are announced, but only if it can make any.

    A client with no `complete_with_tools` is returned untouched. Giving it the
    attribute anyway would make `make_tool_node` believe tools are on offer and
    take the tool-enabled path against a client that cannot serve it.
    """
    if not hasattr(llm, "complete_with_tools"):
        return llm
    return _ToolActivityLLM(llm, announce)


async def _get_or_create_conversation(
    session: AsyncSession, *, conversation_id: int | None, user_id: int
) -> Conversation:
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if conversation.user_id != user_id:
            # Same 404 as "missing" on purpose, so this never confirms that a
            # conversation belonging to someone else exists.
            raise HTTPException(status_code=404, detail="conversation not found")
        return conversation

    conversation = Conversation(user_id=user_id, status=ConversationStatus.ACTIVE)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def _load_state(
    session: AsyncSession, conversation: Conversation
) -> symptom_agent.AllergyState:
    rows = await session.execute(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
    )
    history: list[symptom_agent.ChatMessage] = [
        {"role": m.role.lower(), "content": m.content} for m in rows.scalars().all()
    ]
    state = symptom_agent.initial_state(history)

    latest = await session.execute(
        select(SymptomEvent)
        .where(SymptomEvent.conversation_id == conversation.id)
        .order_by(SymptomEvent.id.desc())
    )
    event = latest.scalars().first()
    if event is not None:
        state["symptoms"] = list(event.symptoms or [])
        state["severity"] = event.severity
        state["duration"] = event.duration
        state["possible_trigger"] = event.possible_trigger
        state["breathing_difficulty"] = event.breathing_difficulty
        state["airway_swelling"] = event.airway_swelling
    return state


def _verdict(result: symptom_agent.AllergyState) -> tuple[str | None, list[str], str | None]:
    """Re-derive the safety verdict for persistence, straight from the engine.

    `_persist_turn` deliberately does NOT copy `result["triage_level"]`. Nothing
    upstream — the model, a tool observation, a future node — can put a verdict
    into the database by writing it into the state dict; it has to survive
    `triage.assess` on the symptoms actually being stored.

    Returns `(level, reasons, rule_version)`, or `(None, [], None)` when the turn
    never reached triage (the graph asked a follow-up question instead). We gate
    on the graph having produced a verdict so that this never *invents* one: an
    unanswered turn must stay unanswered, not be silently triaged on save.
    """
    if result.get("triage_level") is None:
        return None, [], None
    outcome = triage.assess(
        triage.SymptomInput(
            symptoms=result.get("symptoms") or [],
            severity=result.get("severity"),
            breathing_difficulty=bool(result.get("breathing_difficulty")),
            airway_swelling=bool(result.get("airway_swelling")),
        )
    )
    return outcome.level.value, list(outcome.reasons), outcome.rule_version


async def _persist_turn(
    session: AsyncSession,
    conversation: Conversation,
    *,
    user_id: int,
    user_message: str,
    result: symptom_agent.AllergyState,
) -> SymptomEvent | None:
    session.add(
        Message(conversation_id=conversation.id, role=MessageRole.USER, content=user_message)
    )
    verdict_level, verdict_reasons, verdict_version = _verdict(result)

    session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=result.get("assistant_reply") or "",
            # Re-derived by `_verdict`, not copied out of the state dict. Stored
            # on the message so a reloaded conversation can render its verdict
            # without reconstructing the symptom_events -> triage_results join.
            triage_level=verdict_level,
            triage_reasons=verdict_reasons,
        )
    )

    event = SymptomEvent(
        user_id=user_id,
        conversation_id=conversation.id,
        symptoms=result.get("symptoms") or [],
        severity=result.get("severity"),
        duration=result.get("duration"),
        possible_trigger=result.get("possible_trigger"),
        breathing_difficulty=bool(result.get("breathing_difficulty")),
        airway_swelling=bool(result.get("airway_swelling")),
    )
    session.add(event)

    if verdict_level is not None:
        conversation.status = ConversationStatus.COMPLETED

    await session.commit()
    await session.refresh(event)

    if verdict_level is not None:
        session.add(
            TriageResult(
                symptom_event_id=event.id,
                risk_level=verdict_level,
                recommendation=result.get("triage_recommendation"),
                rule_version=verdict_version,
            )
        )
        await session.commit()

    return event


async def _origin_for(session: AsyncSession, user_id: int) -> symptom_agent.NearbyCareOrigin | None:
    """The caller's saved location, or None if they have never set one.

    Half a location is treated as none: a latitude with no longitude would send
    a clinic lookup somewhere in the ocean, and a wrong clinic on a safety path
    is worse than no clinic at all.
    """
    user = await session.get(User, user_id)
    if user is None or user.latitude is None or user.longitude is None:
        return None
    return symptom_agent.NearbyCareOrigin(latitude=user.latitude, longitude=user.longitude)


async def _run_chat(
    req: ChatRequest,
    session: AsyncSession,
    llm: symptom_agent.LLMClient,
    user_id: int,
    conversation: Conversation,
) -> AsyncIterator[str]:
    state = await _load_state(session, conversation)

    # A turn is two sequential model calls plus the rule engine, and a tool
    # lookup in between — several seconds of silence otherwise, which reads as
    # "broken" rather than "working". `run_turn` is synchronous, so it runs on
    # a worker thread and pushes events into a queue that this generator
    # drains, letting the user watch progress happen instead of receiving it
    # all at the end.
    #
    # Both kinds of event ride the same queue so they keep their real order. A
    # `status` stage is an internal step of a model call and is never rendered
    # as a tool invocation; a lookup is reported as its own `tool` event, and
    # the two are never conflated on the client's side.
    pending: queue.Queue[tuple[str, dict]] = queue.Queue()
    announced: list[ToolCallEvent] = []

    def _stage(stage: str) -> None:
        pending.put(("status", {"stage": stage}))

    def _announce(call: ToolCallEvent) -> None:
        announced.append(call)
        pending.put(("tool", call.model_dump(exclude_none=True)))

    yield _sse("status", {"stage": "starting"})

    # Some messages must not reach the model at all (D11). A crisis disclosure
    # answered with a pollen reading, or a dosage question answered with a
    # plausible-sounding number, are the two ways this app could seriously hurt
    # someone. The check is deterministic and it runs before anything else, so
    # there is no phrasing of the question that gets past it and no prompt to
    # talk the model past.
    scope = escalation.assess(req.message)
    if scope.blocks_the_model:
        reply = (
            escalation.crisis_reply(scope)
            if scope.verdict == "crisis"
            else escalation.out_of_scope_reply()
        )
        logger.warning("chat: model bypassed (%s) for user %s", scope.verdict, user_id)
        yield _sse("message", {"delta": reply})
        yield _sse(
            "done",
            {
                "message": reply,
                "conversation_id": conversation.id,
                "symptoms": [],
                "severity": None,
                "duration": None,
                "possible_trigger": None,
                "breathing_difficulty": None,
                "airway_swelling": None,
                # No triage verdict: nothing was assessed, and a level here
                # would be the one number in the turn that nobody computed.
                "triage_level": None,
                "triage_reasons": [],
                "triage_rule_version": None,
                "escalated": scope.verdict,
            },
        )
        return

    # Where "nearby" means. Resolved here, from the user's own saved profile,
    # because the model cannot read the profile and must not be asked for
    # coordinates it has no way to know. A user with no location saved still
    # gets a working tool that declines honestly, rather than a turn where
    # nothing happens.
    origin = await _origin_for(session, user_id)

    task = asyncio.create_task(
        asyncio.to_thread(
            partial(
                symptom_agent.run_turn,
                progress=_stage,
                # The registry the app ships with, so offering tools stays the
                # agent's decision about what exists and never this layer's.
                registry=symptom_agent.default_tool_registry(origin),
            ),
            _with_tool_activity(llm, _announce),
            state,
            req.message,
        )
    )

    while not task.done():
        drained = _drain(pending)
        for name, data in drained:
            yield _sse(name, data)
        if not drained:
            await asyncio.sleep(0.02)

    try:
        result = await task
    except Exception:
        logger.exception("symptom_agent.run_turn failed")
        yield _sse("error", {"detail": "the symptom agent failed to process this message"})
        return

    # Anything that landed between the last poll and completion, before any
    # call is settled below: a `running` always reaches the client before the
    # event that closes it.
    for name, data in _drain(pending):
        yield _sse(name, data)

    # Settle each announced call against the observation the agent recorded for
    # it. The two are appended in the same order, one per call, so index `i` of
    # one belongs to index `i` of the other; a call with no observation at all
    # settles as unfinished rather than as a success.
    observations = result.get("tool_observations") or []
    tool_calls: list[ToolCallEvent] = []
    for index, call in enumerate(announced):
        status, summary, payload, code = _settle(
            observations[index] if index < len(observations) else "", call.name
        )
        # Rebuilt rather than copied: the arguments were what the model asked
        # for at `running`, and they are not part of what the call returned.
        settled = ToolCallEvent(
            id=call.id, name=call.name, status=status, summary=summary, result=payload, code=code
        )
        tool_calls.append(settled)
        yield _sse("tool", settled.model_dump(exclude_none=True))

    yield _sse("status", {"stage": "saving"})

    await _persist_turn(
        session,
        conversation,
        user_id=user_id,
        user_message=req.message,
        result=result,
    )

    reply = result.get("assistant_reply") or ""

    # Incremental delivery of an already-complete string, not provider-side
    # token streaming: `run_turn` is a blocking call that returns the whole
    # reply at once, so nothing can be emitted before it returns. What this buys
    # is that the client receives the text as separate `message` events it can
    # append to, instead of a single payload it can only paint at the end.
    #
    # Each fragment is its own SSE frame, and the loop yields control between
    # them so each frame is written before the next one is produced instead of
    # the server coalescing them back into one. No artificial delay is added —
    # a fake typewriter would make every real turn slower for nothing.
    for index, fragment in enumerate(_fragments(reply)):
        if index:
            await asyncio.sleep(0)
        yield _sse("message", {"delta": fragment})

    payload = ChatResponse(
        message=reply,
        conversation_id=conversation.id,
        symptoms=result.get("symptoms") or [],
        severity=result.get("severity"),
        duration=result.get("duration"),
        possible_trigger=result.get("possible_trigger"),
        breathing_difficulty=result.get("breathing_difficulty"),
        airway_swelling=result.get("airway_swelling"),
        triage_level=result.get("triage_level"),
        triage_reasons=result.get("triage_reasons") or [],
        triage_rule_version=result.get("triage_rule_version"),
        tool_calls=tool_calls or None,
    )
    # `tool_calls` is added to the wire only when a tool actually ran. An
    # absent key and an empty list are different states on the client side, and
    # a client that predates this field must see exactly the payload it saw
    # before, so the default is no key rather than an empty array.
    data = payload.model_dump(exclude={"tool_calls"})
    if payload.tool_calls:
        data["tool_calls"] = [call.model_dump(exclude_none=True) for call in payload.tool_calls]
    yield _sse("done", data)

    # J4: a model-call failure is reported *after* the `done` event, and only
    # when the rule engine did not already reach a verdict on this turn.
    #
    # Order matters for ADR 0001. If extraction failed but the deterministic
    # engine still ran (MAX_QUESTIONS reached, or a previous turn's confirmed
    # fields were enough), `triage_level` is set and the user must see that
    # recommendation — an EMERGENCY instruction is not something to withhold
    # because the provider was flaky. So the error is only emitted when there
    # is no verdict to deliver.
    if result.get("llm_error_kind") and not result.get("triage_level"):
        yield _sse(
            "error",
            {
                "detail": "I could not process that message right now. Please try again.",
                "kind": result["llm_error_kind"],
            },
        )


class _LazyLLMClient:
    """Builds the real client on first use, not at dependency-resolution time.

    Constructing eagerly made a missing `openai_api_key` a 500 on every chat
    request, including ones that should have been rejected as unauthenticated,
    because FastAPI resolves this before the auth dependency runs. Deferring it
    means a misconfigured key surfaces as the stream's `error` event instead.
    """

    # Every instance built so far, so the dev-settings endpoint can drop
    # memoised clients after the key changes mid-process. Without this a client
    # created before the change keeps calling the old key until it is
    # garbage-collected.
    #
    # A WeakSet, not a list: `get_llm` is a per-request dependency, so a plain
    # list would pin one `_LazyLLMClient` — and the `OpenAI` client holding the
    # httpx connection pool it memoises — per request for the life of the
    # process. Those sockets are never closed. Weak refs let a finished request
    # drop its instance while `reset_cached_clients` still reaches the ones
    # genuinely in flight.
    _instances: "WeakSet[_LazyLLMClient]" = WeakSet()

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: symptom_agent.LLMClient | None = None
        _LazyLLMClient._instances.add(self)

    @classmethod
    def reset_cached_clients(cls) -> None:
        for instance in list(cls._instances):
            instance._client = None

    def complete(self, messages) -> str:
        if self._client is None:
            # Use the core factory so OPENAI_BASE_URL (OpenRouter / Azure /
            # local proxy) and OPENAI_MODEL are honoured. The factory returns
            # an object that structurally satisfies symptom_agent.LLMClient.
            from app.core.openai_client import get_openai_client_from_settings

            self._client = get_openai_client_from_settings()
        return self._client.complete(messages)

    def complete_with_tools(self, messages, tools):
        """Delegates the optional tool-calling capability.

        `make_tool_node` duck-types for this method and skips the tool loop
        entirely when it is absent, so a client that only wraps `complete`
        silently opts the whole app out of tools. The wrapper therefore has to
        pass the capability through unchanged rather than hide it.
        """
        if self._client is None:
            from app.core.openai_client import get_openai_client_from_settings

            self._client = get_openai_client_from_settings()
        return self._client.complete_with_tools(messages, tools)


def get_llm() -> symptom_agent.LLMClient:
    """FastAPI dependency so tests can swap in a fake without a real API key."""
    return _LazyLLMClient(get_settings().openai_api_key)


LLMDep = Annotated[symptom_agent.LLMClient, Depends(get_llm)]


@router.post("")
async def chat(
    req: ChatRequest, session: SessionDep, llm: LLMDep, user: CurrentUser
) -> StreamingResponse:
    # Abuse protection. Each turn is a real model call, so an unbounded
    # endpoint is a direct billing risk; auth alone does not bound it.
    #
    # Checked here, before the stream opens, so an over-limit caller gets a
    # real 429 with Retry-After. Raising inside the generator would be too
    # late — the 200 and its headers are already sent by then.
    #
    # The limit is per user, not per conversation: one user must not be able
    # to escape it by starting a fresh conversation each turn.
    decision = await get_limiter().check(str(user.id))
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                "You are sending messages too quickly. "
                f"Please wait about {int(decision.retry_after_seconds) + 1}s and try again."
            ),
            headers=decision.headers,
        )

    # Resolve the conversation before the stream opens. Raising inside the
    # generator would be too late: the 200 and its headers are already sent,
    # so a 404 there would never reach the client.
    conversation = await _get_or_create_conversation(
        session, conversation_id=req.conversation_id, user_id=user.id
    )
    return StreamingResponse(
        _run_chat(req, session, llm, user.id, conversation),
        media_type="text/event-stream",
        headers=decision.headers,
    )
