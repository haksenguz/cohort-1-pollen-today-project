"""Regression tests: negation scope and Korean red-flag aliases (triage.py)."""

import pytest

from app.core.enums import TriageLevel
from app.services import triage


@pytest.mark.parametrize(
    ("symptom", "canonical"),
    [
        # a denial governs only its own clause; the positive clause after "but" wins
        ("no_swelling_but_difficulty_breathing", "difficulty_breathing"),
        ("no_breathing_difficulty_but_throat_closing", "throat_swelling"),
        ("not_chest_tight_but_throat_closing", "throat_swelling"),
        ("without_fever_but_trouble_breathing", "difficulty_breathing"),
        ("no_swelling_하지만_호흡곤란", "difficulty_breathing"),
    ],
)
def test_positive_flag_after_but_is_a_red_flag(symptom: str, canonical: str):
    assert triage.match_red_flag(symptom) == canonical
    out = triage.assess(triage.SymptomInput(symptoms=[symptom], severity=1))
    assert out.level is TriageLevel.EMERGENCY


@pytest.mark.parametrize(
    "symptom",
    [
        "no_breathing_difficulty",
        "no_breathing_difficulty_but_itchy_eyes",
        "nothing_wrong_with_breathing",  # "nothing" is not a negator token
        "notable_itchy_eyes",
    ],
)
def test_denied_flag_with_no_positive_clause_stays_low(symptom: str):
    assert triage.assess(triage.SymptomInput(symptoms=[symptom], severity=1)).level is (
        TriageLevel.LOW
    )


@pytest.mark.parametrize(
    "symptom",
    ["호흡곤란_없음", "숨쉬기힘듦_아님", "목부음없어요", "가슴답답_않아요", "안_숨쉬기힘듦"],
)
def test_korean_denial_is_not_an_emergency(symptom: str):
    assert triage.match_red_flag(symptom) is None


@pytest.mark.parametrize(
    ("symptom", "canonical"),
    [
        ("호흡곤란", "difficulty_breathing"),
        ("숨쉬기 힘듦", "difficulty_breathing"),
        ("숨쉬기힘듦", "difficulty_breathing"),
        ("숨이 차요", "difficulty_breathing"),
        ("목부음", "throat_swelling"),
        ("목이 부었어요", "throat_swelling"),
        ("혀부음", "tongue_swelling"),
        ("혀가 부어요", "tongue_swelling"),
        ("입술부음", "lip_swelling"),
        ("입술이 부어요", "lip_swelling"),
        ("가슴답답", "chest_tightness"),
        ("가슴이 답답해요", "chest_tightness"),
        ("아나필락시스", "anaphylaxis"),
    ],
)
def test_korean_red_flag_is_emergency(symptom: str, canonical: str):
    assert triage.match_red_flag(symptom) == canonical
    out = triage.assess(triage.SymptomInput(symptoms=[symptom], severity=1))
    assert out.level is TriageLevel.EMERGENCY
    assert canonical in out.reasons[0]


def test_korean_ordinary_symptom_stays_low():
    assert triage.assess(triage.SymptomInput(symptoms=["콧물", "재채기"], severity=2)).level is (
        TriageLevel.LOW
    )


def test_rule_version_is_dated_2026_11_17():
    assert triage.RULE_VERSION == "triage-2026-11-17"
