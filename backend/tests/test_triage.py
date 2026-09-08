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
