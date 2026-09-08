"""Offline tests for the symptom agent graph. No network, no real API key —
every LLM call goes through a scripted FakeLLM.

This is the safety-critical seam ADR 0001 describes: the LLM only ever
contributes extracted fields or a follow-up question, and the triage level
that comes back must always be exactly what
`app.services.triage.assess(triage.SymptomInput(...))` would return for
those fields. These tests assert the graph's output against calling the
rule engine directly, not against a hardcoded expectation, so a change to
`triage.py` (out of this task's scope) can't silently desync the two.
"""

import json

from app.agents import symptom_agent
from app.core.enums import TriageLevel
from app.services import triage


class FakeLLM:
    """Returns each entry in `responses` in order, one per `complete()` call.
    A callable entry is invoked with the messages instead of returned as-is,
    for tests that need to branch on what was asked.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, messages):
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        if callable(response):
            return response(messages)
        return response


def _json(**fields) -> str:
    return json.dumps(fields)


# ---------------------------------------------------------------------------
# Happy path: full extraction in one turn hands off to the rule engine.
# ---------------------------------------------------------------------------


def test_full_extraction_in_one_turn_reaches_triage_low():
    llm = FakeLLM(
        [
            _json(
                symptoms=["itchy_eyes", "sneezing"],
                severity=3,
                duration="this morning",
                possible_trigger="pollen",
                breathing_difficulty=False,
                airway_swelling=False,
                ready=True,
            )
        ]
    )
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "My eyes are itchy and I keep sneezing.")

    expected = triage.assess(
        triage.SymptomInput(
            symptoms=["itchy_eyes", "sneezing"],
            severity=3,
            breathing_difficulty=False,
            airway_swelling=False,
        )
    )
    assert result["triage_level"] == expected.level.value
    assert result["triage_level"] == TriageLevel.LOW.value
    assert result["triage_recommendation"] == expected.recommendation
    assert result["triage_reasons"] == expected.reasons
    assert result["triage_rule_version"] == expected.rule_version
    # exactly one LLM call: extraction. Triage is deterministic, not a model call.
    assert len(llm.calls) == 1


def test_emergency_red_flag_reaches_triage_emergency():
    llm = FakeLLM(
        [
            _json(
                symptoms=["throat_swelling"],
                severity=2,
                breathing_difficulty=False,
                airway_swelling=False,
                ready=True,
            )
        ]
    )
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "My throat feels like it's closing up.")

    assert result["triage_level"] == TriageLevel.EMERGENCY.value
    assert "emergency symptoms" in result["triage_reasons"][0]


def test_breathing_difficulty_short_circuits_to_emergency():
    llm = FakeLLM(
        [
            _json(
                symptoms=["sneezing"],
                severity=1,
                breathing_difficulty=True,
                airway_swelling=False,
                ready=True,
            )
        ]
    )
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "I can barely breathe.")

    assert result["triage_level"] == TriageLevel.EMERGENCY.value
    assert result["breathing_difficulty"] is True


# ---------------------------------------------------------------------------
# Multi-turn: incomplete extraction asks a follow-up instead of guessing.
# ---------------------------------------------------------------------------


def test_incomplete_extraction_asks_follow_up_not_triage():
    llm = FakeLLM([_json(symptoms=["sneezing"], ready=False)])
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "I keep sneezing.")

    assert result["triage_level"] is None
    assert result["assistant_reply"]
    assert result["messages"][-1]["role"] == "assistant"


def test_missing_safety_answers_ask_the_safety_question_specifically():
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=4, ready=False)])
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "I keep sneezing, it's pretty bad.")

    assert result["assistant_reply"] == symptom_agent.SAFETY_QUESTION


def test_second_turn_completes_extraction_and_reaches_triage():
    llm = FakeLLM(
        [
            _json(symptoms=["sneezing"], severity=4, ready=False),  # turn 1: asks safety Q
            _json(breathing_difficulty=False, airway_swelling=False, ready=True),  # turn 2
        ]
    )
    state = symptom_agent.initial_state()

    state = symptom_agent.run_turn(llm, state, "I keep sneezing, it's pretty bad.")
    assert state["triage_level"] is None

    result = symptom_agent.run_turn(llm, state, "No trouble breathing, no swelling.")

    assert result["triage_level"] is not None
    assert result["symptoms"] == ["sneezing"]
    assert result["severity"] == 4
    assert result["breathing_difficulty"] is False
    assert result["airway_swelling"] is False


def test_confirmed_true_safety_flag_is_never_downgraded_by_a_later_turn():
    llm = FakeLLM(
        [
            _json(
                symptoms=["throat_swelling"],
                severity=5,
                breathing_difficulty=True,
                airway_swelling=False,
                ready=False,
            ),
            # a garbled / contradicting later extraction tries to say False
            _json(breathing_difficulty=False, ready=True),
        ]
    )
    state = symptom_agent.initial_state()
    state = symptom_agent.run_turn(llm, state, "I can't breathe well and my throat feels tight.")
    result = symptom_agent.run_turn(llm, state, "actually nvm I'm fine")

    assert result["breathing_difficulty"] is True
    assert result["triage_level"] == TriageLevel.EMERGENCY.value


# ---------------------------------------------------------------------------
# Malformed / missing model output must degrade safely, never crash, never
# invent a fact, and never let the LLM assign a triage level.
# ---------------------------------------------------------------------------


def test_non_json_response_does_not_crash_and_sets_extraction_error():
    llm = FakeLLM(["I think you should see a doctor immediately, this is an emergency!"])
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "My eyes are itchy.")

    assert result["extraction_error"] is True
    # the model's free text never becomes a triage verdict
    assert result["triage_level"] is None
    assert result["symptoms"] == []


def test_empty_response_does_not_crash():
    llm = FakeLLM([""])
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "hello")

    assert result["extraction_error"] is True
    assert result["triage_level"] is None


def test_malformed_field_types_are_dropped_not_coerced():
    llm = FakeLLM(
        [
            _json(
                symptoms="sneezing",  # should be a list, not a string
                severity="very bad",  # should be an int
                breathing_difficulty="yes",  # should be a bool
                airway_swelling=None,
                ready=True,
            )
        ]
    )
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "I keep sneezing.")

    # nothing usable was extracted, so the graph must keep asking rather than
    # triage on invented data
    assert result["symptoms"] == []
    assert result["severity"] is None
    assert result["breathing_difficulty"] is None
    assert result["triage_level"] is None


def test_out_of_range_severity_is_dropped():
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=99, ready=False)])
    state = symptom_agent.initial_state()

    result = symptom_agent.run_turn(llm, state, "I keep sneezing.")

    assert result["severity"] is None


def test_llm_raising_is_caught_and_degrades_to_extraction_error():
    class BoomLLM:
        def complete(self, messages):
            raise RuntimeError("network is down")

    state = symptom_agent.initial_state()
    result = symptom_agent.run_turn(BoomLLM(), state, "hello")

    assert result["extraction_error"] is True
    assert result["triage_level"] is None


def test_max_questions_cap_forces_triage_even_with_missing_safety_answers():
    # every turn the model refuses to answer the safety questions; the loop
    # must not run forever and must not silently mark it an emergency.
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=2, ready=False) for _ in range(10)])
    state = symptom_agent.initial_state()

    # MAX_QUESTIONS turns each ask another question; the next one must force triage.
    for _ in range(symptom_agent.MAX_QUESTIONS + 1):
        state = symptom_agent.run_turn(llm, state, "I don't know.")

    assert state["triage_level"] is not None
    # unresolved safety flags default to False (never fabricated True)
    assert state["breathing_difficulty"] is False
    assert state["airway_swelling"] is False


def test_ask_question_llm_failure_falls_back_to_generic_question():
    class FlakyAskLLM:
        def __init__(self):
            self.n = 0

        def complete(self, messages):
            self.n += 1
            if self.n == 1:
                # Safety flags are answered but symptoms/severity are not, so
                # extraction alone is not enough for triage and the graph must
                # reach ask_question's LLM-driven follow-up branch (not the
                # safety-question branch, which never calls the model).
                return _json(
                    symptoms=[],
                    severity=None,
                    breathing_difficulty=False,
                    airway_swelling=False,
                    ready=False,
                )
            raise RuntimeError("boom")

    state = symptom_agent.initial_state()
    result = symptom_agent.run_turn(FlakyAskLLM(), state, "I keep sneezing.")

    assert result["assistant_reply"] == symptom_agent.FALLBACK_QUESTION
    assert result["triage_level"] is None


# ---------------------------------------------------------------------------
# merge_extraction unit tests
# ---------------------------------------------------------------------------


def test_merge_extraction_deduplicates_and_preserves_order():
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["sneezing", "itchy_eyes"]})
    symptom_agent.merge_extraction(state, {"symptoms": ["Itchy Eyes", "nasal_congestion"]})

    assert state["symptoms"] == ["sneezing", "itchy_eyes", "nasal_congestion"]


def test_merge_extraction_ignores_unknown_keys():
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"diagnosis": "anaphylaxis", "severity": 5})

    assert state["severity"] == 5
    assert "diagnosis" not in state
