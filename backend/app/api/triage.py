from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.enums import TriageLevel
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


@router.post("")
async def run_triage(req: TriageRequest) -> TriageResponse:
    outcome = triage.assess(
        triage.SymptomInput(
            symptoms=req.symptoms,
            severity=req.severity,
            breathing_difficulty=req.breathing_difficulty,
            airway_swelling=req.airway_swelling,
        )
    )
    return TriageResponse(
        level=outcome.level,
        recommendation=outcome.recommendation,
        reasons=outcome.reasons,
        rule_version=outcome.rule_version,
    )
