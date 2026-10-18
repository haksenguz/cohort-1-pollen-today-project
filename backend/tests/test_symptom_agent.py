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
from app.agents.symptom_agent import ToolCall, ToolDefinition, ToolRegistry
from app.core.enums import TriageLevel
from app.core.openai_client import ToolTurn
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


# ---------------------------------------------------------------------------
# A confirmed red flag short-circuits intake.
#
# This is the failure the live J3 eval caught. For "숨쉬기 힘들고 목이 부어서
# 부풀었어요" (hard to breathe, throat swollen) the model correctly sets both
# safety flags but returns no severity, so the completeness check said "keep
# asking" and the app replied "when did these symptoms start?" to a user who
# had just said they could not breathe. The rule engine returns EMERGENCY for
# that input no matter what else is known, so asking could only add delay.
# ---------------------------------------------------------------------------


def test_confirmed_breathing_difficulty_triages_without_severity():
    """No symptoms list, no severity, no second flag — and it still triages."""
    llm = FakeLLM(
        [
            _json(
                symptoms=[],
                severity=None,
                breathing_difficulty=True,
                airway_swelling=True,
                ready=False,
            )
        ]
    )

    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "I cannot breathe")

    assert result["triage_level"] == TriageLevel.EMERGENCY.value
    assert result["turn_count"] == 0  # it never asked a follow-up


def test_confirmed_breathing_difficulty_alone_triages():
    """One positive flag is enough; the other may still be unknown."""
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=None, breathing_difficulty=True)])

    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "hard to breathe")

    assert result["triage_level"] == TriageLevel.EMERGENCY.value
    # The unresolved flag is defaulted to False by the rule engine, never True.
    assert result["airway_swelling"] is False


def test_confirmed_airway_swelling_triages_immediately():
    llm = FakeLLM([_json(symptoms=[], severity=None, airway_swelling=True)])

    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "my throat is swollen")

    assert result["triage_level"] == TriageLevel.EMERGENCY.value


def test_red_flag_short_circuit_still_defers_to_the_rule_engine():
    """The shortcut routes; the rule engine still decides the level and reason.

    This is the ADR 0001 guarantee under the new path: the graph did not
    compute EMERGENCY, it handed off to `triage_node` early.
    """
    llm = FakeLLM(
        [_json(symptoms=["sneezing"], severity=1, breathing_difficulty=True, airway_swelling=False)]
    )

    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "can't breathe")

    expected = triage.assess(
        triage.SymptomInput(
            symptoms=["sneezing"],
            severity=1,
            breathing_difficulty=True,
            airway_swelling=False,
        )
    )
    assert result["triage_level"] == expected.level.value
    assert result["triage_reasons"] == expected.reasons
    assert result["triage_rule_version"] == expected.rule_version
    assert "breathing_difficulty reported" in result["triage_reasons"]


def test_an_explicitly_denied_flag_does_not_short_circuit():
    """`breathing_difficulty: false` is an answer, not a red flag. It must keep
    asking, exactly as before."""
    llm = FakeLLM(
        [
            _json(
                symptoms=["sneezing"],
                severity=None,
                breathing_difficulty=False,
                airway_swelling=False,
                ready=False,
            )
        ]
    )

    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "just sneezing")

    assert result["triage_level"] is None
    assert result["turn_count"] == 1


def test_an_unknown_flag_does_not_short_circuit():
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=2, ready=False)])

    result = symptom_agent.run_turn(llm, symptom_agent.initial_state(), "I keep sneezing")

    assert result["triage_level"] is None
    assert result["assistant_reply"] == symptom_agent.SAFETY_QUESTION


def test_the_red_flag_shortcut_does_not_resurrect_a_downgraded_flag():
    """A confirmed True flag stays True across turns, so a later garbled turn
    cannot route past the emergency either."""
    llm = FakeLLM(
        [
            _json(symptoms=["sneezing"], severity=2, breathing_difficulty=True),
            _json(breathing_difficulty=False, ready=True),
        ]
    )
    state = symptom_agent.initial_state()
    state = symptom_agent.run_turn(llm, state, "I cannot breathe")
    assert state["triage_level"] == TriageLevel.EMERGENCY.value

    result = symptom_agent.run_turn(llm, state, "actually I am fine now")

    assert result["breathing_difficulty"] is True
    assert result["triage_level"] == TriageLevel.EMERGENCY.value


# ---------------------------------------------------------------------------
# Progress reporting (chat activity strip).
#
# The stage names are shown to the user while a turn runs, so they are part
# of the product, not just logging. The allow-list below is the guard: this
# agent has no tools and performs no function-calling, so a stage like
# "calling_tool" must never appear, and adding one silently would be the
# first step toward pretending the model decides safety (ADR 0001).
# ---------------------------------------------------------------------------

ALLOWED_STAGES = {"extracting", "asking", "assessing"}


def test_progress_reports_the_extraction_stage() -> None:
    stages: list[str] = []
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=2)])

    symptom_agent.run_turn(llm, symptom_agent.initial_state(), "I am sneezing", stages.append)

    assert stages == ["extracting"]


def test_progress_reports_asking_then_assessing_across_turns() -> None:
    stages: list[str] = []
    llm = FakeLLM(
        [
            _json(symptoms=["sneezing"], breathing_difficulty=False, airway_swelling=False),
            "How long have you had this?",
            _json(symptoms=["sneezing"], severity=2, duration="today"),
        ]
    )

    # Turn 1 asks the model for the next question...
    state = symptom_agent.run_turn(
        llm, symptom_agent.initial_state(), "I am sneezing", stages.append
    )
    assert "asking" in stages

    # ...turn 2 is complete enough to reach the rule engine.
    stages.clear()
    state = symptom_agent.run_turn(llm, state, "started today", stages.append)
    assert "assessing" in stages
    assert state["triage_level"] == TriageLevel.LOW.value


def test_progress_only_ever_emits_known_stages() -> None:
    """No stage may imply a tool call: this agent has none."""
    stages: list[str] = []
    llm = FakeLLM(
        [
            _json(symptoms=["sneezing"], breathing_difficulty=False, airway_swelling=False),
            "How long have you had this?",
            _json(symptoms=["sneezing"], severity=2, duration="today"),
        ]
    )

    state = symptom_agent.run_turn(
        llm, symptom_agent.initial_state(), "I am sneezing", stages.append
    )
    symptom_agent.run_turn(llm, state, "started today", stages.append)

    assert stages
    assert set(stages) <= ALLOWED_STAGES


def test_safety_question_turn_makes_no_question_call_and_reports_no_asking() -> None:
    """With the safety flags unanswered the graph uses SAFETY_QUESTION, a
    constant — so no model call happens and no `asking` stage may be claimed.
    """
    stages: list[str] = []
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=2)])

    state = symptom_agent.run_turn(
        llm, symptom_agent.initial_state(), "I am sneezing", stages.append
    )

    assert state["assistant_reply"] == symptom_agent.SAFETY_QUESTION
    assert "asking" not in stages
    assert len(llm.calls) == 1, "the safety turn should cost exactly one model call"


# ---------------------------------------------------------------------------
# Tool calling: opt-in, read-only, and bounded.
#
# The ReAct seam lives in `make_tool_node`, reached only when a caller passes a
# registry. Everything above this line runs the tool-free graph and must keep
# doing so -- these tests pin that the opt-in is real in both directions: no
# registry means no tool node at all, and a client that cannot call tools is
# unaffected even when a registry is handed to it.
# ---------------------------------------------------------------------------


class ToolCallingFakeLLM:
    """A client that supports the optional `complete_with_tools` capability.

    `tool_turns` is consumed one entry per tool-enabled call. An entry that is
    a tuple of ToolCalls means "call these tools"; a plain string means "answer
    now", and stops the loop. `extraction` is returned by plain `complete`, so
    the graph still finishes the turn after the loop.
    """

    def __init__(self, tool_turns, extraction=None):
        self.tool_turns = list(tool_turns)
        self.extraction = extraction
        self.tool_calls_made = []
        self.complete_calls = 0

    def complete_with_tools(self, messages, tools):
        self.tool_calls_made.append(list(tools))
        turn = self.tool_turns.pop(0)
        if isinstance(turn, str):
            return ToolTurn(content=turn)
        return ToolTurn(content=None, tool_calls=turn)

    def complete(self, messages):
        self.complete_calls += 1
        return self.extraction or _json(symptoms=["sneezing"], severity=2)


def _lookup_tool(**overrides):
    payload = {"name": "Some Clinic", "distance_m": 800}
    defaults = {
        "description": "Look up a nearby clinic.",
        "parameters": {
            "type": "object",
            "properties": {"latitude": {"type": "number"}},
            "required": ["latitude"],
        },
        "result_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "distance_m": {"type": "integer"}},
        },
        "execute": lambda arguments: payload,
        "wired": True,
    }
    defaults.update(overrides)
    return ToolDefinition(name="lookup_clinic", **defaults)


def _tool_call(name="lookup_clinic", arguments=None):
    return ToolCall(id="call_1", name=name, arguments=arguments or {"latitude": 37.5})


def test_graph_without_a_registry_has_no_tool_node():
    """The default graph is the pre-tools graph, node for node."""
    graph = symptom_agent.build_graph(FakeLLM([]))

    assert "tools" not in graph.get_graph().nodes


def test_graph_with_a_registry_adds_the_tool_node_before_extraction():
    graph = symptom_agent.build_graph(
        ToolCallingFakeLLM([]), registry=ToolRegistry([_lookup_tool()])
    )

    assert "tools" in graph.get_graph().nodes


def test_a_registry_does_not_disturb_a_client_that_cannot_call_tools():
    """`complete(messages)` is the whole contract; tools are opt-in on both sides.

    FakeLLM has no `complete_with_tools`, so a registry is simply ignored and
    the turn costs the same one call it always did.
    """
    llm = FakeLLM([_json(symptoms=["sneezing"], severity=2, ready=False)])

    result = symptom_agent.run_turn(
        llm,
        symptom_agent.initial_state(),
        "I am sneezing",
        None,
        ToolRegistry([_lookup_tool()]),
    )

    assert len(llm.calls) == 1
    assert result["triage_level"] is None
    assert result["tool_steps"] == 0
    assert result["tool_observations"] == []


def test_the_tool_loop_observes_a_result_and_then_continues_to_extraction():
    llm = ToolCallingFakeLLM([(_tool_call(),), "There is a clinic 800 m away."])

    result = symptom_agent.run_turn(
        llm,
        symptom_agent.initial_state(),
        "is there a clinic near me? I am sneezing",
        None,
        ToolRegistry([_lookup_tool()]),
    )

    assert result["tool_steps"] == 2
    assert result["tool_observations"] == ['{"name": "Some Clinic", "distance_m": 800}']
    assert llm.complete_calls == 1, "extraction still runs exactly once"


def test_the_model_is_offered_the_registry_schemas():
    llm = ToolCallingFakeLLM(["no lookup needed"])

    symptom_agent.run_turn(
        llm,
        symptom_agent.initial_state(),
        "hello",
        None,
        ToolRegistry([_lookup_tool()]),
    )

    spec = llm.tool_calls_made[0][0]
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "lookup_clinic"
    assert spec["function"]["parameters"]["required"] == ["latitude"]


def test_the_tool_loop_is_bounded_by_max_tool_steps():
    """A model that only ever calls tools still stops."""
    llm = ToolCallingFakeLLM([(_tool_call(),) for _ in range(20)])

    result = symptom_agent.make_tool_node(llm, ToolRegistry([_lookup_tool()]))(
        {**symptom_agent.initial_state(), "messages": [{"role": "user", "content": "clinic?"}]}
    )

    assert result["tool_steps"] == symptom_agent.MAX_TOOL_STEPS
    assert len(llm.tool_calls_made) == symptom_agent.MAX_TOOL_STEPS
    assert len(result["tool_observations"]) == symptom_agent.MAX_TOOL_STEPS


def test_an_unknown_tool_name_is_observed_as_an_error_not_a_crash():
    llm = ToolCallingFakeLLM([(_tool_call(name="book_appointment"),), "sorry"])

    result = symptom_agent.make_tool_node(llm, ToolRegistry([_lookup_tool()]))(
        {**symptom_agent.initial_state(), "messages": [{"role": "user", "content": "book me in?"}]}
    )

    assert result["tool_observations"] == ["error: that lookup is not available."]


def test_an_observation_never_names_the_tool():
    """Every failure sentence is generic, including the hallucinated-name case.

    `book_appointment` is a name the model invented; putting it in the
    observation would surface an internal identifier on a user-facing path.
    The model loses nothing — the transcript hands it its own `name` next to
    the observation — so the name is logged server-side and kept out of text.
    """
    llm = ToolCallingFakeLLM([(_tool_call(name="book_appointment"),), "sorry"])

    result = symptom_agent.make_tool_node(llm, ToolRegistry([_lookup_tool()]))(
        {**symptom_agent.initial_state(), "messages": [{"role": "user", "content": "book me in?"}]}
    )

    assert "book_appointment" not in result["tool_observations"][0]


def test_a_tool_that_raises_degrades_to_an_observation():
    def _boom(arguments):
        raise RuntimeError("provider down")

    llm = ToolCallingFakeLLM([(_tool_call(),), "sorry"])

    result = symptom_agent.make_tool_node(llm, ToolRegistry([_lookup_tool(execute=_boom)]))(
        {**symptom_agent.initial_state(), "messages": [{"role": "user", "content": "clinic?"}]}
    )

    assert result["tool_observations"] == ["error: that lookup failed."]


def test_an_llm_failure_during_the_tool_loop_ends_the_loop_quietly():
    class BoomToolLLM:
        def complete_with_tools(self, messages, tools):
            raise RuntimeError("network is down")

    result = symptom_agent.make_tool_node(BoomToolLLM(), ToolRegistry([_lookup_tool()]))(
        symptom_agent.initial_state()
    )

    # The loop gave up after one attempt and observed nothing, so extraction
    # runs on the conversation alone -- a dead tool layer cannot end a turn.
    assert result["tool_steps"] == 1
    assert result["tool_observations"] == []


def test_tool_observations_never_become_extracted_fields():
    """The loop's output is context for the next node, not state to merge."""
    llm = ToolCallingFakeLLM(
        [(_tool_call(arguments={"latitude": 37.5, "severity": 9}),), "here you go"],
        extraction=_json(symptoms=["sneezing"], ready=False),
    )

    result = symptom_agent.run_turn(
        llm, symptom_agent.initial_state(), "clinic?", None, ToolRegistry([_lookup_tool()])
    )

    assert result["severity"] is None
    assert result["symptoms"] == ["sneezing"]
    assert "Some Clinic" not in result["triage_reasons"]
