"""Rule-based safety triage (documentation §4, §23).

The LLM extracts structured symptoms; this engine — never the LLM — decides the
safety level. Deterministic, testable, auditable. Emergency red flags short-
circuit everything else.
"""

from dataclasses import dataclass, field

from app.core.enums import TriageLevel

RULE_VERSION = "triage-2026-09-07"

# Red-flag symptom keywords that force an emergency regardless of severity score.
EMERGENCY_SYMPTOMS = {
    "throat_swelling",
    "tongue_swelling",
    "lip_swelling",
    "difficulty_breathing",
    "chest_tightness",
    "fainting",
    "anaphylaxis",
}


@dataclass
class SymptomInput:
    symptoms: list[str] = field(default_factory=list)
    severity: int | None = None  # 0-10
    breathing_difficulty: bool = False
    airway_swelling: bool = False


@dataclass
class TriageOutcome:
    level: TriageLevel
    recommendation: str
    reasons: list[str]
    rule_version: str = RULE_VERSION


def assess(s: SymptomInput) -> TriageOutcome:
    reasons: list[str] = []

    # 1) hard emergency gates
    if s.breathing_difficulty:
        reasons.append("breathing_difficulty reported")
    if s.airway_swelling:
        reasons.append("airway_swelling reported")
    flagged = EMERGENCY_SYMPTOMS.intersection({x.lower() for x in s.symptoms})
    if flagged:
        reasons.append(f"emergency symptoms: {', '.join(sorted(flagged))}")

    if reasons:
        return TriageOutcome(
            level=TriageLevel.EMERGENCY,
            recommendation=(
                "These may be signs of a serious allergic reaction. Seek emergency "
                "care now or call your local emergency number."
            ),
            reasons=reasons,
        )

    # 2) severity-based moderate/low
    sev = s.severity or 0
    if sev >= 7:
        return TriageOutcome(
            level=TriageLevel.MODERATE,
            recommendation=(
                "Your symptoms are significant. Consider contacting a healthcare "
                "professional; we can help you find a nearby clinic."
            ),
            reasons=[f"severity {sev} >= 7"],
        )

    return TriageOutcome(
        level=TriageLevel.LOW,
        recommendation=(
            "Symptoms look mild. Monitor them, reduce exposure to your triggers, and "
            "follow your usual allergy-management plan."
        ),
        reasons=[f"severity {sev} < 7, no red flags"],
    )
