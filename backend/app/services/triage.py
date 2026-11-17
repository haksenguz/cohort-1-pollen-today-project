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

RULE_VERSION = "triage-2026-11-17"

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
        # Korean. Spaced and unspaced forms both appear: normalisation turns
        # spaces into "_", so "숨쉬기 힘듦" arrives as "숨쉬기_힘듦".
        "호흡곤란",
        "호흡_곤란",
        "숨쉬기힘",
        "숨쉬기_힘",
        "숨쉬기어려",
        "숨쉬기_어려",
        "숨이차",
        "숨이_차",
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
        # Korean: 목이 부음 / 목부음 (throat swelling), 목이 붓다.
        "목부음",
        "목_부음",
        "목이부",
        "목이_부",
        "목이붓",
        "목이_붓",
    ),
    "tongue_swelling": (
        "tongue_swelling",
        "swollen_tongue",
        "tongue_swell",
        "tongue_closing",
        "swelling_tongue",
        # Korean: 혀가 부음 / 혀부음.
        "혀부음",
        "혀_부음",
        "혀가부",
        "혀가_부",
        "혀가붓",
        "혀가_붓",
    ),
    "lip_swelling": (
        "lip_swelling",
        "swollen_lips",
        "swollen_lip",
        "lips_swelling",
        "lip_closing",
        # Korean: 입술이 부음 / 입술부음.
        "입술부음",
        "입술_부음",
        "입술이부",
        "입술이_부",
        "입술이붓",
        "입술이_붓",
    ),
    "chest_tightness": (
        "chest_tightness",
        "chest_tight",
        "tight_chest",
        "chest_pressure",
        "chest_squeezing",
        # Korean: 가슴이 답답 / 가슴답답.
        "가슴답답",
        "가슴_답답",
        "가슴이답답",
        "가슴이_답답",
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
        # Korean: 아나필락시스 (and the short form that the model may return).
        "아나필락시",
    ),
}

# A denial must not trip a red flag, but only when the denial governs the
# flag directly. The guard reads the clause the negator starts or ends, so a
# compound like "no_swelling_but_difficulty_breathing" still matches its second
# clause. Leading English negators need the underscore so "nothing" or "notable"
# never count.
_NEGATED_LEADS = (
    "no_",
    "not_",
    "without_",
    "denies_",
    "deny_",
    "never_",
    "free_of_",
    # Korean: 안 (not) and 없이 (without) before the symptom.
    "안_",
    "없이_",
)
# Korean denial endings: 없음 / 없어요 (none), 아님 / 아니에요 (not), 않아요 (does not).
_NEGATED_TAILS = (
    "없음",
    "없어",
    "없어요",
    "없습니다",
    "아님",
    "아니요",
    "아니에요",
    "않음",
    "않아",
    "않아요",
    "않습니다",
)
# Words that join two clauses. A positive red flag after one of these still counts.
_CLAUSE_JOINERS = ("but", "하지만")


def _normalize(symptom: str) -> str:
    return symptom.strip().lower().replace(" ", "_").replace("-", "_")


def _clauses(normalized: str) -> list[str]:
    """Split on joiners so each clause can be negated (or not) on its own."""
    groups: list[list[str]] = [[]]
    for token in normalized.split("_"):
        if token in _CLAUSE_JOINERS:
            groups.append([])
        elif token:
            groups[-1].append(token)
    return ["_".join(g) for g in groups if g]


def _is_denied(clause: str) -> bool:
    return clause.startswith(_NEGATED_LEADS) or clause.endswith(_NEGATED_TAILS)


def is_negated(symptom: str) -> bool:
    """True when the whole string opens with a denial of what follows."""
    return _is_denied(_normalize(symptom))


def match_red_flag(symptom: object) -> str | None:
    """Return the canonical red flag this symptom represents, or None.

    Exact membership in `EMERGENCY_SYMPTOMS` is checked first. Otherwise each
    clause (split on "but") is checked in order: a denied clause is skipped,
    and the first clause that contains an alias decides the flag.

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
    for clause in _clauses(normalized):
        if _is_denied(clause):
            continue
        for canonical, aliases in RED_FLAG_ALIASES.items():
            if any(alias in clause for alias in aliases):
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
