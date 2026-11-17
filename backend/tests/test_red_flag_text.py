import pytest

from app.services.red_flag_text import scan


@pytest.mark.parametrize(
    "text",
    [
        "I can't breathe",
        "my throat is closing and I have trouble breathing",
        "숨쉬기 힘들고 목이 부어서 부풀었어요",
        "my tongue is swelling",
    ],
)
def test_confirms_flags(text):
    assert any(scan(text))


@pytest.mark.parametrize(
    "text",
    [
        "my eyes are itchy",
        "no trouble breathing, just sneezing",
        "숨쉬기 힘들지 않아요",
        "how much pollen today",
    ],
)
def test_no_false_positive(text):
    assert scan(text) == (False, False)


def test_outage_with_red_flag_still_emergency_and_clean_outage_gives_no_verdict():
    from app.agents.symptom_agent import triage_node

    # Outage, nothing usable, nothing confirmed: no verdict.
    s = triage_node({"llm_error_kind": "unavailable", "messages": []})
    assert not s.get("triage_level")
    # Outage but the text confirmed a red flag: the engine decides EMERGENCY.
    s = triage_node({"llm_error_kind": "unavailable", "breathing_difficulty": True, "messages": []})
    assert s["triage_level"] == "EMERGENCY"
