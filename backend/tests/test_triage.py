import pytest

from app.core.enums import TriageLevel
from app.services import triage


def test_breathing_difficulty_is_emergency():
    out = triage.assess(triage.SymptomInput(severity=2, breathing_difficulty=True))
    assert out.level is TriageLevel.EMERGENCY


def test_airway_swelling_is_emergency():
    out = triage.assess(triage.SymptomInput(severity=1, airway_swelling=True))
    assert out.level is TriageLevel.EMERGENCY


def test_red_flag_symptom_is_emergency_even_with_low_severity():
    out = triage.assess(triage.SymptomInput(symptoms=["sneezing", "throat_swelling"], severity=1))
    assert out.level is TriageLevel.EMERGENCY


def test_high_severity_is_moderate():
    out = triage.assess(triage.SymptomInput(symptoms=["sneezing"], severity=8))
    assert out.level is TriageLevel.MODERATE


def test_mild_is_low():
    out = triage.assess(triage.SymptomInput(symptoms=["itchy_eyes"], severity=3))
    assert out.level is TriageLevel.LOW


def test_rule_version_is_recorded():
    out = triage.assess(triage.SymptomInput(severity=0))
    assert out.rule_version == triage.RULE_VERSION


# ---------------------------------------------------------------------------
# Red-flag aliases. The symptom strings reaching this engine are written by a
# language model, which paraphrases. These cases are the real ones the live
# model produced during the J3 eval, and each one scored LOW before the alias
# table existed — i.e. the app told a user whose throat was closing that their
# symptoms looked mild. This is the regression net for that.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("symptom", "canonical"),
    [
        # what the live model actually returned
        ("throat_closing", "throat_swelling"),
        ("anaphylactic_reaction", "anaphylaxis"),
        ("breathing_difficulty", "difficulty_breathing"),
        # and the paraphrases it might return tomorrow
        ("chest_tight", "chest_tightness"),
        ("swollen_tongue", "tongue_swelling"),
        ("tongue_swell", "tongue_swelling"),
        ("cant_breathe", "difficulty_breathing"),
        ("trouble_breathing", "difficulty_breathing"),
        ("tight_chest", "chest_tightness"),
        ("passed_out", "fainting"),
        ("swollen_lips", "lip_swelling"),
    ],
)
def test_red_flag_alias_is_emergency(symptom: str, canonical: str):
    assert triage.match_red_flag(symptom) == canonical
    out = triage.assess(triage.SymptomInput(symptoms=[symptom], severity=1))
    assert out.level is TriageLevel.EMERGENCY
    assert canonical in out.reasons[0]


@pytest.mark.parametrize(
    "symptom",
    [
        "itchy_eyes",
        "sneezing",
        "runny_nose",
        "nasal_congestion",
        "headache",
        "watery_eyes",
        "rash_on_arms",
        "cough",
    ],
)
def test_ordinary_symptoms_are_not_red_flags(symptom: str):
    """The alias table must not inflate every symptom into an emergency."""
    assert triage.match_red_flag(symptom) is None
    assert triage.assess(triage.SymptomInput(symptoms=[symptom], severity=2)).level is (
        TriageLevel.LOW
    )


@pytest.mark.parametrize(
    "symptom",
    [
        "no_breathing_difficulty",
        "not_difficulty_breathing",
        "without_trouble_breathing",
        "denies_chest_tightness",
        "no_throat_swelling",
        "never_fainting",
    ],
)
def test_a_negated_red_flag_is_not_an_emergency(symptom: str):
    """A denial must not trip the gate.

    The extraction prompt tells the model to report only what the user has, but
    a string like `no_breathing_difficulty` is easy to produce and would
    otherwise be read as the red flag it names.
    """
    assert triage.match_red_flag(symptom) is None
    assert triage.assess(triage.SymptomInput(symptoms=[symptom], severity=1)).level is (
        TriageLevel.LOW
    )


def test_red_flag_aliases_do_not_hide_an_exact_match():
    """Exact canonical names still resolve to themselves."""
    for name in triage.EMERGENCY_SYMPTOMS:
        assert triage.match_red_flag(name) == name


def test_red_flag_survives_severity_and_extra_symptoms():
    """A red flag among ordinary symptoms still wins, and the reason lists it."""
    out = triage.assess(
        triage.SymptomInput(
            symptoms=["sneezing", "itchy_eyes", "throat_closing"],
            severity=1,
        )
    )

    assert out.level is TriageLevel.EMERGENCY
    assert "throat_swelling" in out.reasons[0]


def test_match_red_flag_normalizes_case_and_separators():
    assert triage.match_red_flag("Throat Closing") == "throat_swelling"
    assert triage.match_red_flag("throat-closing") == "throat_swelling"
    assert triage.match_red_flag("  CHEST_TIGHT  ") == "chest_tightness"


def test_alias_table_has_no_entries_outside_the_canonical_set():
    """Every alias table key must be a real red flag, or the two can drift."""
    assert set(triage.RED_FLAG_ALIASES) == triage.EMERGENCY_SYMPTOMS


def test_no_red_flag_alias_collides_with_another_flags_canonical_name():
    """A symptom must resolve to exactly one red flag, and the right one.

    If `chest_tight` were an alias of `throat_swelling`, a chest complaint
    would be escalated (correctly) but reported under the wrong red flag in
    `reasons`, which is what a clinician reads. The mapping must be
    unambiguous: no alias may contain another flag's canonical name.
    """
    for other in triage.EMERGENCY_SYMPTOMS:
        for canonical, aliases in triage.RED_FLAG_ALIASES.items():
            if canonical == other:
                continue
            for alias in aliases:
                assert other not in alias, (
                    f"{other!r} is a substring of {canonical}'s alias {alias!r}, "
                    "so that alias would be attributed to the wrong red flag"
                )


def test_each_alias_resolves_to_exactly_one_red_flag():
    """Every alias in the table maps back to the flag it belongs to."""
    for canonical, aliases in triage.RED_FLAG_ALIASES.items():
        for alias in aliases:
            assert triage.match_red_flag(alias) == canonical, (
                f"alias {alias!r} resolved to {triage.match_red_flag(alias)!r}, "
                f"expected {canonical!r}"
            )


def test_a_parsed_malformed_entry_does_not_crash_the_engine():
    """`assess` is called with model-derived data; a non-string must not 500."""
    out = triage.assess(triage.SymptomInput(symptoms=[None, 5, "throat_closing"], severity=1))

    assert out.level is TriageLevel.EMERGENCY
