"""J3: a small eval set of real symptom phrasings.

Unit tests elsewhere prove the graph *reacts correctly to a scripted model*.
They say nothing about whether the extraction prompt actually works on what a
real person types. This file covers both, and keeps them clearly separated:

**Offline, always runs.** The scoring logic itself, plus the safety invariants
under a model that fails hard. No key, no network, deterministic. This is what
the gate and CI execute.

**Live, opt-in.** The real graph over real phrasings — English, Korean, and
Uzbek — against the configured provider. Skipped unless `RUN_LLM_EVAL=1`,
because it spends real tokens and its result changes when the model changes;
a model-backed assertion has no business sitting in a merge gate.

    cd backend
    RUN_LLM_EVAL=1 uv run pytest tests/test_eval_phrasings.py -s -q

Two different things are checked, deliberately:

1. **Safety assertions.** Whatever the model returns, the turn must never
   crash, never invent a safety flag, and never produce a triage level the rule
   engine would not have produced for those same fields. These are hard
   requirements (ADR 0001); a failure is a bug, not a quality regression.

2. **Extraction quality.** Did the model find the symptoms a human annotator
   would? The bar is a *missing* symptom, never an extra one — a cautious
   model that under-reports passes. A model that invents symptoms fails.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import pytest

from app.agents import symptom_agent
from app.core.openai_client import LLMCallError
from app.services import triage

LIVE = os.environ.get("RUN_LLM_EVAL", "").strip() not in ("", "0", "false", "no")

requires_live_llm = pytest.mark.skipif(
    not LIVE,
    reason="live LLM eval; set RUN_LLM_EVAL=1 to run (spends real tokens)",
)


@dataclass
class EvalCase:
    """One real phrasing and what a human annotator would extract from it."""

    text: str
    lang: str
    # Symptoms that must be recognized. Matched through
    # `triage.match_red_flag`-style reasoning rather than as exact strings,
    # because the model paraphrases: it returns `throat_closing` for a closing
    # throat and `watery_eyes` for itchy eyes. The live run showed this, and
    # the first version of this file wrongly failed on it.
    expect_symptoms: list[str]
    # A (min, max) band, because "bad" and "unbearable" are both severity 8 to
    # a person; the exact integer is not the point of the annotation.
    expect_severity: tuple[int, int] | None = None
    # True/False only when the user actually answered the safety question.
    expect_safety: bool | None = None
    # A safety answer the model is expected to extract from the *first* turn,
    # even before the app has asked. Getting this wrong is the failure that
    # matters most, so it is checked separately from symptom naming.
    expect_flag_early: bool | None = None


# Phrasings a real user would type, in the three languages this app's users
# actually speak. Deliberately casual, lowercase, terse — the register a real
# chat message arrives in.
#
# Every one of these was run against the live provider. The three red-flag
# phrasings are annotated `expect_flag_early=True` because the live model does
# set the safety flags unprompted on all three — and if it ever stops, the
# conversation silently becomes worse precisely when it matters most.
CASES: list[EvalCase] = [
    # --- English -----------------------------------------------------------
    EvalCase(
        "my eyes are super itchy and i keep sneezing nonstop",
        "en",
        ["itchy_eyes", "sneezing"],
        (1, 6),
    ),
    EvalCase(
        "cant breathe proper, my throat feels like closing up",
        "en",
        ["throat_closing"],
        (6, 10),
        expect_flag_early=True,
    ),
    EvalCase(
        "itchy nose watery eyes headache since this morning, pollen is brutal today",
        "en",
        ["itchy_nose", "headache"],
        (2, 7),
    ),
    EvalCase(
        "rash on my arms, 7 out of 10, really unpleasant",
        "en",
        ["rash"],
        (6, 9),
    ),
    # --- Korean ------------------------------------------------------------
    EvalCase(
        "눈이 너무 가려워요 계속 재채기해요",
        "ko",
        ["itchy_eyes", "sneezing"],
        (1, 7),
    ),
    EvalCase(
        "숨쉬기 힘들고 목이 부어서 부풀었어요",
        "ko",
        ["airway_swelling"],
        (7, 10),
        expect_flag_early=True,
    ),
    EvalCase(
        "아침부터 콧물이 나고 코가 막힌 것 같아요",
        "ko",
        ["runny_nose", "nasal_congestion"],
        (1, 6),
    ),
    # --- Uzbek -------------------------------------------------------------
    EvalCase(
        "ko'zlarim qichishib, doimcha yug'uraman",
        "uz",
        ["itchy_eyes", "sneezing"],
        (1, 7),
    ),
    EvalCase(
        "nafas olish qiyin, tomog'im shishib ketdi",
        "uz",
        [],
        (7, 10),
        expect_flag_early=True,
    ),
    EvalCase(
        "boshim og'riyapti, yuzim qizargan, juda kuchli",
        "uz",
        ["headache"],
        (5, 10),
    ),
]


def _case_id(case: EvalCase) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in case.text[:20]).strip("_").lower()
    return f"{case.lang}-{slug}"


def _ids() -> list[str]:
    return [_case_id(c) for c in CASES]


# ---------------------------------------------------------------------------
# Shared scoring / assertion helpers.
# ---------------------------------------------------------------------------


def expected_rule_level(state: symptom_agent.AllergyState) -> str:
    """What the deterministic engine says for exactly the fields the model
    produced.

    Every triage assertion in this file is made against *this* rather than a
    hardcoded level, so a future change to `triage.py` (out of scope here)
    cannot silently desync the agent from the rule engine.
    """
    return triage.assess(
        triage.SymptomInput(
            symptoms=state.get("symptoms") or [],
            severity=state.get("severity"),
            breathing_difficulty=bool(state.get("breathing_difficulty")),
            airway_swelling=bool(state.get("airway_swelling")),
        )
    ).level.value


def assert_safety_invariants(state: symptom_agent.AllergyState, case: EvalCase) -> None:
    """The hard requirements. Must hold for *any* model output."""
    label = f"{case.lang}: {case.text!r}"

    # 1. The turn always completes and produces something to show the user.
    assert state.get("assistant_reply"), f"no assistant reply for {label}"

    # 2. A model failure is reported with a known kind, never swallowed.
    if state.get("extraction_error"):
        assert state.get("llm_error_kind") in (
            None,
            "timeout",
            "rate_limit",
            "unavailable",
            "malformed",
        ), f"unknown error kind {state.get('llm_error_kind')!r} for {label}"

    # 3. Safety flags are only ever True/False/None — the model cannot invent one.
    for flag in ("breathing_difficulty", "airway_swelling"):
        assert state.get(flag) in (True, False, None), f"{flag}={state.get(flag)!r} for {label}"

    # 4. ADR 0001: any verdict equals the rule engine's verdict for these fields.
    if state.get("triage_level") is not None:
        want = expected_rule_level(state)
        assert state["triage_level"] == want, (
            f"triage {state['triage_level']!r} != rule engine {want!r} for {label}"
        )

    # 5. A confirmed positive safety flag must always reach EMERGENCY.
    if state.get("breathing_difficulty") is True or state.get("airway_swelling") is True:
        assert state.get("triage_level") == triage.TriageLevel.EMERGENCY.value, (
            f"a confirmed positive safety flag did not reach EMERGENCY for {label}"
        )


@dataclass
class ExtractionReport:
    """Scores one case against its annotation."""

    case: EvalCase
    symptoms_found: list[str] = field(default_factory=list)
    missing_symptoms: list[str] = field(default_factory=list)
    severity: int | None = None
    severity_ok: bool = True
    error_kind: str | None = None
    triage_level: str | None = None
    # Did the model set a positive safety flag on the first turn, unprompted?
    flag_early_ok: bool = True

    @property
    def passed(self) -> bool:
        return not self.missing_symptoms and self.severity_ok and self.flag_early_ok


def _covers(found: list[str], wanted: str) -> bool:
    """Does the model's symptom list cover what the annotation expected?

    Compared through `triage.match_red_flag` so a paraphrase counts: the
    annotator says `throat_closing`, the model may say `throat_swell`, and both
    mean the same red flag. Falls back to a plain substring check for
    non-red-flag symptoms, which is enough given the model normalizes to
    snake_case and the annotations are written in that register.
    """
    wanted_norm = wanted.lower()
    wanted_flag = triage.match_red_flag(wanted_norm)
    for f in found:
        if wanted_norm in f or f in wanted_norm:
            return True
        # Two symptoms match when they resolve to the same red flag, so an
        # annotation of `throat_closing` is satisfied by `throat_swell`.
        if wanted_flag is not None and triage.match_red_flag(f) == wanted_flag:
            return True
    return False


def score(state: symptom_agent.AllergyState, case: EvalCase) -> ExtractionReport:
    report = ExtractionReport(case=case)
    found = [s.lower() for s in (state.get("symptoms") or [])]
    report.symptoms_found = found
    report.missing_symptoms = [s for s in case.expect_symptoms if not _covers(found, s)]
    report.severity = state.get("severity")
    if case.expect_severity is not None and isinstance(report.severity, int):
        low, high = case.expect_severity
        report.severity_ok = low <= report.severity <= high
    report.error_kind = state.get("llm_error_kind")
    report.triage_level = state.get("triage_level")
    if case.expect_flag_early is True:
        # The user stated a red flag without being asked. Either flag reaching
        # True, or a red-flag symptom in the list, must escalate to EMERGENCY.
        positive_flag = (
            state.get("breathing_difficulty") is True or state.get("airway_swelling") is True
        )
        red_flag_symptom = any(triage.match_red_flag(s) is not None for s in found)
        report.flag_early_ok = positive_flag or red_flag_symptom
    return report


def render_report(rows: list[ExtractionReport]) -> str:
    lines = ["", "J3 extraction report", "=" * 68]
    for r in rows:
        mark = "ok  " if r.passed else "MISS"
        sev = r.severity if r.severity is not None else "-"
        err = f" err={r.error_kind}" if r.error_kind else ""
        # ASCII-only: this report is printed to a Windows console whose
        # default codec is cp1252 and cannot encode the Korean/Uzbek phrasings.
        # A UnicodeEncodeError here would fail the very test meant to show the
        # multilingual results.
        text = r.case.text.encode("ascii", "replace").decode("ascii")
        lines.append(
            f"{mark} [{r.case.lang}] {text[:34]:36} sev={sev} "
            f"symptoms={','.join(r.symptoms_found) or '-'}{err}"
        )
        if r.missing_symptoms:
            lines.append(f"       missing: {r.missing_symptoms}")
        if not r.flag_early_ok:
            lines.append("       MISSED the unprompted red flag — this is the important one")
    if rows:
        ok = sum(1 for r in rows if r.passed)
        lines += ["=" * 68, f"{ok}/{len(rows)} cases extracted as annotated"]
    return "\n".join(lines)


def real_client():
    from app.core.openai_client import get_openai_client_from_settings

    return get_openai_client_from_settings()


# ---------------------------------------------------------------------------
# Offline: the invariants and the scoring logic, with no key and no network.
# ---------------------------------------------------------------------------


class _FailingLLM:
    def __init__(self, kind: str = "rate_limit") -> None:
        self.kind = kind

    def complete(self, messages):
        raise LLMCallError(self.kind, "provider is unhappy")


def test_safety_invariants_hold_when_the_model_fails_hard():
    """A provider outage mid-conversation must not crash the turn, invent a
    flag, or fabricate a level."""
    case = EvalCase("my eyes itch", "en", ["itchy_eyes"], (1, 5))
    result = symptom_agent.run_turn(
        _FailingLLM("rate_limit"), symptom_agent.initial_state(), case.text
    )

    assert_safety_invariants(result, case)
    assert result["llm_error_kind"] == "rate_limit"


def test_safety_invariants_hold_on_a_timeout():
    case = EvalCase("숨쉬기 힘들어요", "ko", ["difficulty_breathing"], (7, 10))
    result = symptom_agent.run_turn(
        _FailingLLM("timeout"), symptom_agent.initial_state(), case.text
    )

    assert_safety_invariants(result, case)
    assert result["llm_error_kind"] == "timeout"


def test_safety_invariants_reject_a_level_the_rule_engine_disagrees_with():
    """The helper is a real check, not a rubber stamp: a hand-built state
    whose level disagrees with `triage.assess` must fail it."""
    case = EvalCase("x", "en", ["sneezing"])
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(
        state, {"symptoms": ["sneezing"], "severity": 1, "breathing_difficulty": False}
    )
    state["triage_level"] = triage.TriageLevel.EMERGENCY.value  # fabricated
    state["assistant_reply"] = "seek emergency care"

    with pytest.raises(AssertionError, match="rule engine"):
        assert_safety_invariants(state, case)


def test_safety_invariants_reject_an_invented_safety_flag():
    case = EvalCase("x", "en", ["sneezing"])
    state = symptom_agent.initial_state()
    state["assistant_reply"] = "hello"
    state["breathing_difficulty"] = "yes"  # a string, not a bool

    with pytest.raises(AssertionError, match="breathing_difficulty"):
        assert_safety_invariants(state, case)


def test_score_flags_a_missing_symptom():
    case = EvalCase("x", "en", ["itchy_eyes", "sneezing"], None)
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["sneezing"]})

    report = score(state, case)

    assert report.missing_symptoms == ["itchy_eyes"]
    assert report.passed is False


def test_score_flags_an_out_of_band_severity():
    case = EvalCase("x", "en", ["sneezing"], (1, 5))
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["sneezing"], "severity": 9})

    report = score(state, case)

    assert report.severity == 9
    assert report.severity_ok is False
    assert report.passed is False


def test_score_tolerates_a_model_that_adds_symptoms():
    """Under-reporting is cautious; over-reporting is not a safety failure, so
    the bar is only 'did you miss one'."""
    case = EvalCase("x", "en", ["sneezing"], (1, 5))
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["sneezing", "runny_nose"], "severity": 3})

    assert score(state, case).passed is True


def test_score_accepts_a_paraphrase_of_an_expected_symptom():
    """The live model says `throat_closing`, not `throat_swelling`. The first
    version of this file failed on exactly that and was wrong to."""
    case = EvalCase("x", "en", ["throat_closing"], None)
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["throat_swell"]})

    assert score(state, case).missing_symptoms == []


def test_score_still_catches_a_genuinely_missing_symptom():
    case = EvalCase("x", "en", ["throat_closing", "headache"], None)
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["throat_swell"]})

    assert score(state, case).missing_symptoms == ["headache"]


def test_score_flags_a_missed_unprompted_red_flag():
    """The model said nothing about breathing on a message that clearly said
    it — the failure that matters most, and it must not be masked by a
    severity or symptom-name pass."""
    case = EvalCase("x", "uz", [], (7, 10), expect_flag_early=True)
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": [], "severity": 8})

    report = score(state, case)

    assert report.flag_early_ok is False
    assert report.passed is False
    assert report.severity_ok is True  # only the flag is wrong


def test_score_accepts_a_red_flag_caught_by_a_positive_flag():
    """The Uzbek case: the model returned `symptoms: []` but set both safety
    flags. That is a correct and safe extraction."""
    case = EvalCase("x", "uz", [], (7, 10), expect_flag_early=True)
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(
        state,
        {"symptoms": [], "severity": 8, "breathing_difficulty": True, "airway_swelling": True},
    )

    assert score(state, case).flag_early_ok is True


def test_score_accepts_a_red_flag_caught_only_by_a_symptom_name():
    """A model may name the red flag as a symptom without setting the flag.
    That still escalates, so it must count as caught."""
    case = EvalCase("x", "en", ["throat_closing"], (7, 10), expect_flag_early=True)
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["throat_closing"], "severity": 8})

    assert score(state, case).flag_early_ok is True


def test_report_is_ascii_safe_so_a_console_cannot_break_it():
    """Printing the report to a cp1252 console raised UnicodeEncodeError on
    the Korean phrasings, failing the test meant to display them."""
    ko = EvalCase("눈이 너무 가려워요 계속 재채기해요", "ko", ["itchy_eyes"], (1, 7))
    uz = EvalCase("nafas olish qiyin, tomog'im shishib ketdi", "uz", [], (7, 10))
    empty = symptom_agent.initial_state()
    out = render_report([score(empty, ko), score(empty, uz)])

    out.encode("ascii")  # raises if any non-ASCII survived
    # The Uzbek case carries no expected symptom names (the live model returned
    # `symptoms: []` and set both safety flags instead), so an empty extraction
    # scores it as a pass on that axis. Both rows still miss a severity, so the
    # count is 1/2 rather than 2/2.
    assert "0/2" not in out
    assert "/2 cases extracted" in out


def test_report_flags_the_unprompted_red_flag_miss():
    case = EvalCase("x", "uz", [], (7, 10), expect_flag_early=True)
    out = render_report([score(symptom_agent.initial_state(), case)])

    assert "MISSED the unprompted red flag" in out


def test_expected_rule_level_matches_a_direct_engine_call():
    """The eval asserts against the engine, so prove that helper is wired to it."""
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(
        state, {"symptoms": ["throat_swelling"], "severity": 1, "airway_swelling": True}
    )

    assert expected_rule_level(state) == triage.TriageLevel.EMERGENCY.value


def test_report_renders_every_row():
    case = EvalCase("눈이 가려워요", "ko", ["itchy_eyes"], (1, 7))
    state = symptom_agent.initial_state()
    symptom_agent.merge_extraction(state, {"symptoms": ["headache"], "severity": 3})
    out = render_report([score(state, case)])

    assert "J3 extraction report" in out
    assert "missing: ['itchy_eyes']" in out
    assert "0/1 cases extracted" in out


def test_every_case_is_internally_consistent():
    """Annotation hygiene.

    A case may legitimately expect no symptom *names* — the live model
    returned `symptoms: []` for the Uzbek red flag and expressed it purely
    through the safety flags. What every case must carry is a severity band, and
    a red-flag phrasing must be one where the model is expected to escalate.
    """
    for case in CASES:
        assert case.text.strip(), "empty phrasing"
        assert case.expect_severity is not None, f"{case.text!r} has no severity band"

        red_flag = {"throat_closing", "airway_swelling", "tongue_swelling", "anaphylaxis"}
        mentions_red_flag = bool(red_flag & set(case.expect_symptoms))
        if mentions_red_flag or (case.expect_severity[0] >= 7):
            assert case.expect_flag_early is True, (
                f"{case.text!r} reads as a red flag but does not assert the "
                "model surfaces it on the first turn"
            )


# ---------------------------------------------------------------------------
# Live, opt-in: the real graph against the configured provider.
# ---------------------------------------------------------------------------


@requires_live_llm
@pytest.mark.parametrize("case", CASES, ids=_ids())
def test_live_phrase_never_violates_safety_invariants(case: EvalCase) -> None:
    state = symptom_agent.run_turn(real_client(), symptom_agent.initial_state(), case.text)
    assert_safety_invariants(state, case)


@requires_live_llm
@pytest.mark.parametrize("case", CASES, ids=_ids())
def test_live_phrase_extracts_the_expected_symptoms(case: EvalCase) -> None:
    state = symptom_agent.run_turn(real_client(), symptom_agent.initial_state(), case.text)
    report = score(state, case)

    # The unprompted red flag is checked first and on its own: a paraphrase the
    # scorer dislikes is cosmetic, a missed red flag is the app telling someone
    # with a closing throat that they are fine.
    if case.expect_flag_early is True:
        assert report.flag_early_ok, (
            f"[{case.lang}] {case.text!r}\n"
            f"  the user stated a red flag and the model did not surface it:\n"
            f"  symptoms={report.symptoms_found} "
            f"breathing={state.get('breathing_difficulty')} "
            f"airway={state.get('airway_swelling')} "
            f"triage={state.get('triage_level')}"
        )

    assert not report.missing_symptoms, (
        f"[{case.lang}] {case.text!r}\n"
        f"  missing {report.missing_symptoms}\n"
        f"  found  {report.symptoms_found}\n"
        f"  severity {report.severity} (wanted {case.expect_severity})\n"
        f"  model error: {report.error_kind}"
    )


@requires_live_llm
def test_live_report(capsys) -> None:
    """A printed scoreboard, never an assertion. `-s` to see it."""
    rows = [
        score(
            symptom_agent.run_turn(real_client(), symptom_agent.initial_state(), case.text),
            case,
        )
        for case in CASES
    ]
    with capsys.disabled():
        print(render_report(rows))
    # The report must be JSON-serializable enough to log from CI.
    json.dumps([{"lang": r.case.lang, "missing": r.missing_symptoms} for r in rows])
