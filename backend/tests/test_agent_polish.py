import json

from app.agents import symptom_agent


class _Scripted:
    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)

    def complete(self, messages):  # noqa: ARG002
        return self._replies.pop(0)


def _extraction(**fields) -> str:
    return json.dumps(fields)


def test_the_safety_question_is_preceded_by_an_acknowledgement():
    llm = _Scripted(_extraction(symptoms=["sneezing"], ack="I hear the sneezing."))
    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "I keep sneezing")
    assert result["assistant_reply"] == f"I hear the sneezing.\n\n{symptom_agent.SAFETY_QUESTION}"


def test_the_safety_question_follows_the_users_language():
    llm = _Scripted(_extraction(symptoms=["sneezing"], ack="재채기가 나시는군요."))
    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "재채기가 계속 나요")
    assert result["assistant_reply"].endswith(symptom_agent.SAFETY_QUESTION_KO)


def test_a_bad_acknowledgement_is_dropped_not_shown():
    llm = _Scripted(_extraction(symptoms=["sneezing"], ack="x" * 500))
    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "I keep sneezing")
    assert result["assistant_reply"] == symptom_agent.SAFETY_QUESTION


def test_a_pollen_question_points_to_the_today_tab():
    llm = _Scripted(_extraction(symptoms=[], ack="Sure, I can help with that."))
    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "what's the pollen today?")
    assert result["assistant_reply"].startswith(symptom_agent.TODAY_POINTER)
    assert "Sure" not in result["assistant_reply"]


def test_lookup_intent_gate():
    def state(text):
        return {"messages": [{"role": "user", "content": text}]}

    assert symptom_agent._wants_lookup(state("which clinic is near me"))
    assert symptom_agent._wants_lookup(state("근처 병원 알려줘"))
    assert symptom_agent._wants_lookup(state("I can't breathe"))
    assert not symptom_agent._wants_lookup(state("my eyes are itchy"))
    assert not symptom_agent._wants_lookup(state("I take medication every day"))
