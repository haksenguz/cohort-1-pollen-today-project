"""Standalone triage endpoint (documentation §4, §23, ADR 0001).

`POST /api/triage` lets a client submit structured symptoms directly (no
conversation required) and get a safety verdict back. Same safety boundary as
`app/api/chat.py`: this module never decides urgency itself, it only calls the
deterministic `app.services.triage.assess` and persists what that engine
returned. The emergency short-circuit lives entirely in `triage.py` — this
endpoint just records the result faithfully.

Auth: requires a bearer token. `symptom_events.user_id` is a NOT NULL foreign
key (see `app/models/__init__.py`), so persisting a symptom event has always
needed an identity; the endpoint was public only because nothing was written
to the database yet. Now that it persists, anonymous submissions have nowhere
to attach, so this follows the same `CurrentUser` pattern `chat.py` uses.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.db import SessionDep
from app.core.enums import TriageLevel
from app.core.security import CurrentUser
from app.models import SymptomEvent, TriageResult
from app.services import triage

router = APIRouter(prefix="/api/triage", tags=["triage"])


class TriageRequest(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    severity: int | None = Field(default=None, ge=0, le=10)
    breathing_difficulty: bool = False
    airway_swelling: bool = False


class TriageResponse(BaseModel):
    level: TriageLevel
    recommendation: str
    reasons: list[str]
    rule_version: str
    symptom_event_id: int
    triage_result_id: int


@router.post("")
async def run_triage(req: TriageRequest, session: SessionDep, user: CurrentUser) -> TriageResponse:
    # 1) The deterministic engine decides the verdict. Nothing here inspects
    #    symptoms or picks a level; this call is the only source of `outcome`.
    outcome = triage.assess(
        triage.SymptomInput(
            symptoms=req.symptoms,
            severity=req.severity,
            breathing_difficulty=req.breathing_difficulty,
            airway_swelling=req.airway_swelling,
        )
    )

    # 2) Persist the extracted symptoms, then the verdict against them,
    # mirroring the 1:N symptom_events -> triage_results split from ADR 0001.
    # This never feeds back into `outcome` — persistence cannot change a
    # verdict that was already decided above.
    event = SymptomEvent(
        user_id=user.id,
        conversation_id=None,
        symptoms=req.symptoms,
        severity=req.severity,
        breathing_difficulty=req.breathing_difficulty,
        airway_swelling=req.airway_swelling,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    result = TriageResult(
        symptom_event_id=event.id,
        risk_level=outcome.level,
        recommendation=outcome.recommendation,
        rule_version=outcome.rule_version,
    )
    session.add(result)
    await session.commit()
    await session.refresh(result)

    return TriageResponse(
        level=outcome.level,
        recommendation=outcome.recommendation,
        reasons=outcome.reasons,
        rule_version=outcome.rule_version,
        symptom_event_id=event.id,
        triage_result_id=result.id,
    )
