"""Out-of-scope detection and a real escalation path (D11).

Two jobs, both of which have to happen *before* the model is allowed to answer.

**Why before.** The failure this prevents is the model improvising a medical
answer it should not give. A prompt instruction asking it to decline is a
request; this is a branch that removes the request. Nothing reaches the LLM on
these paths, so there is no phrasing of the question that gets past it.

**Why deterministic.** A classifier that runs in the model is a classifier the
model can be talked out of, and it changes answer when the model is retrained.
This is keyword and pattern matching in ordinary Python, so it is testable, it
is reviewable, and a safety reviewer can read exactly what it matches on.

The scope boundary is drawn from how regulators describe this class of app. The
MHRA symptom-checker guidance puts "software that only signposts the user to
suitable care e.g. see your GP, go to A&E" in the *unlikely to be a medical
device* column, while software that "provides the diagnosis by itself" or
"claims it can perform, or support the function of, a clinician" is on the other
side of the line. This app signs a user off to the right service. It does not
diagnose, name a condition, or dose anything, and the refusal below is the code
that holds that line.

Detection is keyword-based and therefore incomplete — it will miss a crisis
expressed in a language it has no terms for, or in terms nobody thought of. That
limitation is stated in the user-facing copy rather than hidden. It is a net
that catches what it recognises, not a detector that proves absence.

Two specific gaps, recorded so nobody assumes better coverage than exists:

- The composer invites the user to write "in any language", and the patterns
  are per-language. A request mixed across two languages — `무슨 Disease is
  this` — will not match, because the Korean branch needs 질병 next to 무슨 and
  the English branch needs "what disease". Korean and English are both covered;
  code-switched phrasing is not.
- A crisis described only in body language (`기분이 가라앉아요`) matches
  nothing. The net catches the explicit cases and misses the implicit ones.

Both are reasons this is a safety net rather than a guarantee, and both are
reasons a crisis line number belongs in the app's chrome rather than only in
this branch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# Korean mental-health crisis services. 1393 is the national suicide-prevention
# counselling line, 1333 the mental-health crisis line. Both are 24h.
CRISIS_LINES: tuple[tuple[str, str], ...] = (
    ("1393", "자살예방 상담전화"),
    ("1333", "정신건강 위기상담"),
)

# Physical emergency. Already produced by the triage engine, but listed here so
# the escalation message is complete on its own and does not depend on the
# caller having run triage first.
EMERGENCY_NUMBER = "119"

# Deliberately specific. Bare 자살 alone would be enough, but a term like 죽다
# appears in innocuous sentences ("the pollen kills the plants"), and a crisis
# banner that fires on ordinary conversation trains people to ignore it.
_CRISIS_PATTERNS = re.compile(
    r"""
    자\s*살 |                      # 자살, 자 살
    자\s*해 |                      # 자해
    목\s*숨\s*을\s*끊 |             # 목숨을 끊다 (끊, not 끓)
    죽\s*고\s*싶 |                 # 죽고 싶다
    살\s*고\s*싶 |                 # 살고 싶다
    끝\s*내\s*고\s*싶 |            # 끝내고 싶다
    자\s*살\s*예\s*방 |            # 자살예방
    자\s*해\s*진\s*단 |            # 자해진단
    self[\s-]?harm | suicidal | suicide | kill\s+myself | end\s+my\s+life
    | want\s+to\s+die | take\s+my\s+own\s+life
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Requests the app must refuse rather than answer. These are *requests*, not
# topics: someone describing a rash is fine and gets a real answer, someone
# asking "what disease is this" is not and does not.
#
# No trailing `|`. In VERBOSE mode a trailing alternation adds an empty branch
# that matches at position 0, so the pattern fires on literally every message
# and the app refuses to answer anything at all.
_OUT_OF_SCOPE_PATTERNS = re.compile(
    r"""
    무슨\s*질병 | 어떤\s*질병 | 뭔\s*질병                    # what disease
    | 진단\s*해\s*줘 | 진단\s*해\s*주세요                 # diagnose me
    | 약을?\s*얼마 | 약\s*처방 | 약을?\s*먹                # dosage / prescribing
    | 투여량 | 복용량
    | 검사\s*결과\s*解读 | 검사\s*결과\s*해석             # interpret results
    | (알레르기)?\s*약이?\s*(맞|이\s*맞) | 약이\s*맞                 # is this the right drug
    | 처방전
    | what\s+(disease|condition|allergen)\s+(is|am\s+i)\s+i
    | (diagnose|diagnos)\s+(me|this)
    | (how\s+much|what\s+dose|dosage)
    | (prescribe|prescription)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

ScopeVerdict = Literal["in_scope", "out_of_scope", "crisis"]


@dataclass(frozen=True)
class Escalation:
    """Why the model is not being asked, and what the user is told instead."""

    verdict: ScopeVerdict
    reason: str | None = None
    lines: tuple[tuple[str, str], ...] = ()

    @property
    def blocks_the_model(self) -> bool:
        return self.verdict != "in_scope"


def assess(text: str) -> Escalation:
    """Classify one user message. Pure, synchronous, no I/O."""
    body = (text or "").strip()
    if not body:
        return Escalation(verdict="in_scope")

    # Crisis outranks everything. Someone typing "I can't breathe and I want to
    # die" must not be handed a pollen reading, and must not be handed a
    # refusal about prescribing either.
    if _CRISIS_PATTERNS.search(body):
        return Escalation(
            verdict="crisis",
            reason="The message describes self-harm or wanting to die.",
            lines=CRISIS_LINES,
        )

    if _OUT_OF_SCOPE_PATTERNS.search(body):
        return Escalation(
            verdict="out_of_scope",
            reason="The message asks for a diagnosis, a drug, or a dose.",
        )

    return Escalation(verdict="in_scope")


def crisis_reply(escalation: Escalation) -> str:
    """What to say when someone says they want to die.

    The one line that must not change: **nobody is reading this.** An app that
    implies a human will see the message is worse than one that stays silent,
    because it spends the exact moment someone reached out.
    """
    lines = "\n".join(f"- **{number}** — {name}" for number, name in escalation.lines)
    return (
        "I'm sorry you're dealing with this. You deserve to talk to someone right now.\n\n"
        f"**If you are in immediate danger, call {EMERGENCY_NUMBER}.**\n\n"
        f"You can call, free and 24 hours a day:\n{lines}\n\n"
        "One important thing: **nobody at this app reads these messages.** There is no "
        "team watching this chat and no one will reply to you here. The numbers above "
        "are staffed. Please use them."
    )


def out_of_scope_reply() -> str:
    """What to say when asked for a diagnosis, a drug, or a dose.

    Says what the app can and cannot do, then does the signposting rather than
    leaving the user at a refusal.
    """
    return (
        "I can't give a diagnosis, name a condition, or recommend a medicine or a dose — "
        "getting that right needs an examination and someone who can prescribe.\n\n"
        "What I can do is help you work out **how urgent this is**, check today's pollen "
        "and air quality, and find a clinic near you. For a diagnosis or treatment, "
        "please book with a doctor — an 알레르기과 (allergy clinic) if it is allergy-related."
    )
