"""Personal-data access and deletion (개인정보 보호법 제4조 / 제35조 / 제36조).

Two rights this module exists to honour:

- **Access and transmission** (제4조3, 제35조) — the user can see what is held
  about them and take a copy of it. That is a *transmission* right, not just a
  view right, so `export_user_data` returns the whole thing as one document
  rather than a paginated list they would have to scrape.
- **Correction and deletion** (제36조) — and 제36조③ is the clause that shapes
  the implementation: when deleting, it must be impossible to recover or
  regenerate. So there is no soft-delete flag and no tombstone row. The rows
  are removed and the account is gone.

`environment_snapshots` is deliberately absent from both. It has no `user_id`
and holds observed pollen and air quality for a *location*, not for a person —
it is shared cache, and deleting it on one account's exit would destroy data
other accounts still read. The one thing that does hold a location is
`hospital_searches`, which is a user's own search history and does get deleted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.models import (
    Alert,
    Conversation,
    HospitalResult,
    HospitalSearch,
    Message,
    NotificationPreference,
    SymptomEvent,
    TriageResult,
    User,
    UserAllergy,
)

# Never leaves the server, in an export or an error. A "download my data"
# endpoint that returns the password hash is a credential-disclosure bug wearing
# a privacy feature's clothes.
_NEVER_EXPORTED = {"password_hash"}


def _row(model_row: Any, *, drop: set[str] | None = None) -> dict[str, Any]:
    """One row as a JSON-safe dict."""
    out: dict[str, Any] = {}
    for column in model_row.__table__.columns:
        name = column.name
        if name in _NEVER_EXPORTED or name in (drop or ()):
            continue
        value = getattr(model_row, name, None)
        out[name] = value.isoformat() if isinstance(value, datetime) else value
    return out


async def _all(session: AsyncSession, model: Any, *where: Any) -> list[Any]:
    """Rows for one model.

    `session.execute(...).scalars()` rather than SQLModel's `session.exec()`:
    `app.core.db` builds plain `sqlalchemy.ext.asyncio.AsyncSession`, which has
    no `exec`. The exec form reads like it works and 500s at runtime.
    """
    result = await session.execute(select(model).where(*where))
    return list(result.scalars().all())


async def export_user_data(session: AsyncSession, *, user_id: int) -> dict[str, Any]:
    """Everything held about one user, as one document.

    Nested rather than flat, because a flat dump of eleven tables is not
    something a person can check: the point of an export is that the user can
    read it and see that it matches what they remember telling the app.
    """
    user = await session.get(User, user_id)
    if user is None:
        return {}

    conversations = await _all(session, Conversation, Conversation.user_id == user_id)
    events = await _all(session, SymptomEvent, SymptomEvent.user_id == user_id)
    searches = await _all(session, HospitalSearch, HospitalSearch.user_id == user_id)
    allergies = await _all(session, UserAllergy, UserAllergy.user_id == user_id)
    alerts = await _all(session, Alert, Alert.user_id == user_id)

    # Children gathered by parent id in one query each, rather than a query per
    # conversation: an account with a few hundred turns should not cost a few
    # hundred round-trips to export or delete itself.
    conversation_ids = [c.id for c in conversations if c.id is not None]
    messages = (
        await _all(session, Message, Message.conversation_id.in_(conversation_ids))
        if conversation_ids
        else []
    )
    event_ids = [e.id for e in events if e.id is not None]
    verdicts = (
        await _all(session, TriageResult, TriageResult.symptom_event_id.in_(event_ids))
        if event_ids
        else []
    )
    search_ids = [s.id for s in searches if s.id is not None]
    results = (
        await _all(session, HospitalResult, HospitalResult.hospital_search_id.in_(search_ids))
        if search_ids
        else []
    )

    preferences = await session.get(NotificationPreference, user_id)

    messages_by_conversation: dict[int, list[dict[str, Any]]] = {}
    for message in messages:
        messages_by_conversation.setdefault(message.conversation_id, []).append(_row(message))

    verdicts_by_event: dict[int, dict[str, Any]] = {
        v.symptom_event_id: _row(v) for v in verdicts if v.symptom_event_id is not None
    }
    events_out: list[dict[str, Any]] = []
    for event in events:
        row = _row(event)
        # The engine's verdict belongs with the symptoms it was derived from, so
        # the export cannot be read as "this is what you said" alone.
        verdict = verdicts_by_event.get(event.id)
        if verdict is not None:
            row["triage_result"] = verdict
        events_out.append(row)

    results_by_search: dict[int, list[dict[str, Any]]] = {}
    for result in results:
        results_by_search.setdefault(result.hospital_search_id, []).append(_row(result))
    searches_out: list[dict[str, Any]] = []
    for search in searches:
        row = _row(search)
        row["results"] = results_by_search.get(search.id, [])
        searches_out.append(row)

    conversations_out: list[dict[str, Any]] = []
    for conversation in conversations:
        row = _row(conversation)
        row["messages"] = messages_by_conversation.get(conversation.id, [])
        conversations_out.append(row)

    return {
        "exported_at": datetime.now().astimezone().isoformat(),
        "format": "allergy-ai/personal-data/v1",
        "account": _row(user),
        "notification_preferences": _row(preferences) if preferences is not None else None,
        "allergies": [_row(a) for a in allergies],
        "conversations": conversations_out,
        "symptom_events": events_out,
        "alerts": [_row(a) for a in alerts],
        "hospital_searches": searches_out,
        "counts": {
            "conversations": len(conversations),
            "messages": len(messages),
            "symptom_events": len(events),
            "triage_results": len(verdicts),
            "alerts": len(alerts),
            "allergies": len(allergies),
            "hospital_searches": len(searches),
            "hospital_results": len(results),
        },
    }


async def delete_user_account(session: AsyncSession, *, user_id: int) -> dict[str, int]:
    """Remove every row belonging to one user, children first.

    Order is the whole correctness of this function. `messages`, `triage_results`
    and `hospital_results` have no `user_id` of their own, so a delete that
    goes table by table on `user_id` leaves them behind as orphans whose foreign
    key points at a user that no longer exists.

    The caller commits. If anything raises, nothing is committed and the account
    is intact: a half-deleted account is worse than a failed delete, because
    the user believes their data is gone and it is not.
    """
    removed: dict[str, int] = {}

    conversations = await _all(session, Conversation, Conversation.user_id == user_id)
    conversation_ids = [c.id for c in conversations if c.id is not None]
    events = await _all(session, SymptomEvent, SymptomEvent.user_id == user_id)
    event_ids = [e.id for e in events if e.id is not None]
    searches = await _all(session, HospitalSearch, HospitalSearch.user_id == user_id)
    search_ids = [s.id for s in searches if s.id is not None]

    if conversation_ids:
        removed["messages"] = len(
            await _all(session, Message, Message.conversation_id.in_(conversation_ids))
        )
        await session.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
    else:
        removed["messages"] = 0

    if event_ids:
        removed["triage_results"] = len(
            await _all(session, TriageResult, TriageResult.symptom_event_id.in_(event_ids))
        )
        await session.execute(
            delete(TriageResult).where(TriageResult.symptom_event_id.in_(event_ids))
        )
    else:
        removed["triage_results"] = 0

    if search_ids:
        removed["hospital_results"] = len(
            await _all(session, HospitalResult, HospitalResult.hospital_search_id.in_(search_ids))
        )
        await session.execute(
            delete(HospitalResult).where(HospitalResult.hospital_search_id.in_(search_ids))
        )
    else:
        removed["hospital_results"] = 0

    for model, key in (
        (SymptomEvent, "symptom_events"),
        (HospitalSearch, "hospital_searches"),
        (Conversation, "conversations"),
        (Alert, "alerts"),
        (UserAllergy, "allergies"),
        (NotificationPreference, "notification_preferences"),
    ):
        column = model.__table__.columns["user_id"]
        rows = await _all(session, model, column == user_id)
        removed[key] = len(rows)
        if rows:
            await session.execute(delete(model).where(column == user_id))

    user = await session.get(User, user_id)
    if user is not None:
        await session.delete(user)
        removed["account"] = 1
    else:
        removed["account"] = 0

    return removed
