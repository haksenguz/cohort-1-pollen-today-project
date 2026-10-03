"""Rule-based safety triage (documentation §4, §23).

The LLM extracts structured symptoms; this engine — never the LLM — decides the
safety level. Deterministic, testable, auditable. Emergency red flags short-
circuit everything else.

Red-flag matching is deliberately *fuzzy*, and that is a safety requirement, not
a nicety. The symptom strings this engine receives are written by a language
model, which does not reliably use our canonical names: asked about "my throat
feels like closing up" the live model returns `throat_closing`, not
`throat_swelling`, and asked about anaphylaxis it returns
`anaphylactic_reaction`. An exact-string gate scored `throat_closing`,
`chest_tight` and `anaphylactic_reaction` as LOW — telling a user whose throat
is closing that their symptoms look mild. So each red flag owns a list of
aliases and a symptom matches if any alias appears in it.

This stays a rule engine (ADR 0001). The alias table is a static, auditable
list of substrings; no model is consulted, and a reviewer can read the whole
decision in this file.
"""

from dataclasses import dataclass, field

from app.core.enums import TriageLevel

RULE_VERSION = "triage-2026-10-03"

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

# Aliases per red flag. Matched as substrings of the normalized symptom string,
# because the model paraphrases freely. Keep this list conservative: every entry
# here can turn a LOW/MODERATE turn into an EMERGENCY, so only unambiguous
# red-flag phrasings belong in it. A word that is merely *associated* with
# breathing (e.g. "wheezing" on its own) is deliberately not an alias unless it
# is on the `difficulty_breathing` list below, which the model only emits when
# breathing itself is compromised.
RED_FLAG_ALIASES: dict[str, tuple[str, ...]] = {
    "difficulty_breathing": (
        "difficulty_breathing",
        "breathing_difficulty",
        "difficulty_to_breath",
        "hard_to_breath",
        "trouble_breathing",
        "trouble_with_breathing",
        "breathless",
        "shortness_of_breath",
        "cannot_breathe",
        "cant_breathe",
        "struggling_to_breath",
    ),
    "throat_swelling": (
        "throat_swelling",
        "swollen_throat",
        "throat_swell",
        "throat_closing",
        "throat_closes",
        "throat_tight",
        "throat_closing_up",
        "neck_swelling",
        "swollen_neck",
    ),
    "tongue_swelling": (
        "tongue_swelling",
        "swollen_tongue",
        "tongue_swell",
        "tongue_closing",
        "swelling_tongue",
    ),
    "lip_swelling": (
        "lip_swelling",
        "swollen_lips",
        "swollen_lip",
        "lips_swelling",
        "lip_closing",
    ),
    "chest_tightness": (
        "chest_tightness",
        "chest_tight",
        "tight_chest",
        "chest_pressure",
        "chest_squeezing",
    ),
    "fainting": (
        "fainting",
        "fainted",
        "blackout",
        "unconscious",
        "passed_out",
        "lost_consciousness",
    ),
    "anaphylaxis": (
        "anaphylaxis",
        "anaphylactic",
        "anaphylactic_reaction",
        "anaphylactic_shock",
    ),
}

# A symptom string that *negates* the finding must not match. The model is
# instructed to report only what the user has, but a defensive negation guard
# costs nothing and prevents a string like "no_breathing_difficulty" from
# matching the `difficulty_breathing` aliases above.
_NEGATION_PREFIXES = (
    "no",
    "not",
    "without",
    "denies",
    "deny",
    "never",
    "free_of",
)


def _normalize(symptom: str) -> str:
    return symptom.strip().lower().replace(" ", "_").replace("-", "_")


def is_negated(symptom: str) -> bool:
    """True when the string reads as a denial of what follows."""
    parts = _normalize(symptom).split("_")
    return any(p in _NEGATION_PREFIXES for p in parts[:2])


def match_red_flag(symptom: object) -> str | None:
    """Return the canonical red flag this symptom represents, or None.

    Exact membership in `EMERGENCY_SYMPTOMS` is checked first, then the alias
    table as substrings. A negated string returns None.

    Takes `object` because the strings arriving here are model-extracted and
    this function is on the safety path: a non-string entry must be ignored,
    never raise. A malformed entry can only ever *miss* a red flag, which the
    flags and the rest of the list still cover, and a crash here would be far
    worse than a missed synonym.
    """
    if not isinstance(symptom, str):
        return None
    normalized = _normalize(symptom)
    if normalized in EMERGENCY_SYMPTOMS:
        return normalized
    if is_negated(normalized):
        return None
    for canonical, aliases in RED_FLAG_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return canonical
    return None


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
    # Match each symptom through the alias table so a paraphrase like
    # `throat_closing` still counts as the `throat_swelling` red flag.
    flagged = {m for x in s.symptoms if (m := match_red_flag(x)) is not None}
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
