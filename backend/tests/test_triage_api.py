"""`POST /api/triage`: auth boundary, persistence, and the emergency path.

Two layers, same split `test_chat_api.py` uses and explains:

- The auth boundary (`test_triage_rejects_anonymous_callers`) goes through the
  real HTTP app with the shared `client` fixture (User/UserAllergy tables
  only). It fails before touching `symptom_events`, so SQLite's inability to
  compile that table's JSONB column never comes up.
- Persistence and the emergency short-circuit call the router function
  directly with a fake session that just records what would have been
  written, instead of a real engine. This exercises the full mapping from
  `triage.assess()` output to `SymptomEvent`/`TriageResult` fields --
  including that an emergency verdict is recorded as `EMERGENCY`, unmodified
  -- without needing a Postgres-only JSONB column SQLite cannot create.
  Not covered here: an actual round trip through a real (Postgres) database.
"""

from dataclasses import dataclass, field

import pytest

from app.api import triage as triage_api
from app.core.enums import TriageLevel
from app.models import SymptomEvent, TriageResult, User


@dataclass
class _FakeSession:
    """Records `.add()`, assigns ids on `.commit()`, no SQL involved."""

    added: list = field(default_factory=list)
    _next_id: int = 1

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    async def refresh(self, obj) -> None:
        return None


def _user(user_id: int = 7) -> User:
    return User(id=user_id, email="triage-user@example.com", password_hash="x")


@pytest.mark.asyncio
async def test_triage_rejects_anonymous_callers(client) -> None:
    res = await client.post("/api/triage", json={"symptoms": ["sneezing"], "severity": 2})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_low_severity_persists_symptom_event_and_triage_result() -> None:
    session = _FakeSession()
    req = triage_api.TriageRequest(symptoms=["itchy_eyes"], severity=3)

    resp = await triage_api.run_triage(req, session, _user())

    assert resp.level is TriageLevel.LOW
    events = [o for o in session.added if isinstance(o, SymptomEvent)]
    results = [o for o in session.added if isinstance(o, TriageResult)]
    assert len(events) == 1
    assert len(results) == 1

    event = events[0]
    assert event.user_id == 7
    assert event.conversation_id is None
    assert event.symptoms == ["itchy_eyes"]
    assert event.severity == 3
    assert event.breathing_difficulty is False
    assert event.airway_swelling is False

    result = results[0]
    assert result.symptom_event_id == event.id
    assert result.risk_level == TriageLevel.LOW
    assert result.rule_version == "triage-2026-09-07"

    assert resp.symptom_event_id == event.id
    assert resp.triage_result_id == result.id


@pytest.mark.asyncio
async def test_high_severity_persists_moderate() -> None:
    session = _FakeSession()
    req = triage_api.TriageRequest(symptoms=["sneezing"], severity=8)

    resp = await triage_api.run_triage(req, session, _user())

    assert resp.level is TriageLevel.MODERATE
    result = next(o for o in session.added if isinstance(o, TriageResult))
    assert result.risk_level == TriageLevel.MODERATE


@pytest.mark.asyncio
async def test_breathing_difficulty_short_circuits_to_emergency_and_is_recorded() -> None:
    session = _FakeSession()
    req = triage_api.TriageRequest(symptoms=["sneezing"], severity=1, breathing_difficulty=True)

    resp = await triage_api.run_triage(req, session, _user())

    # Unmistakable in the response.
    assert resp.level is TriageLevel.EMERGENCY
    assert any("breathing_difficulty" in r for r in resp.reasons)

    # Unmistakable in what got persisted -- the low severity score never
    # waters the recorded verdict down.
    event = next(o for o in session.added if isinstance(o, SymptomEvent))
    result = next(o for o in session.added if isinstance(o, TriageResult))
    assert event.breathing_difficulty is True
    assert result.risk_level == TriageLevel.EMERGENCY
    assert result.symptom_event_id == event.id


@pytest.mark.asyncio
async def test_red_flag_symptom_short_circuits_to_emergency_even_with_low_severity() -> None:
    session = _FakeSession()
    req = triage_api.TriageRequest(symptoms=["sneezing", "throat_swelling"], severity=1)

    resp = await triage_api.run_triage(req, session, _user())

    assert resp.level is TriageLevel.EMERGENCY
    result = next(o for o in session.added if isinstance(o, TriageResult))
    assert result.risk_level == TriageLevel.EMERGENCY
