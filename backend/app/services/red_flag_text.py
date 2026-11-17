"""Deterministic red-flag scan over what the user actually typed.

ADR 0001 says the rule engine owns every safety decision. Until now the engine
only saw flags the *model* extracted, so a provider outage, or a model that
misses a phrase, meant a user writing "I can't breathe" got no verdict. This is
a plain regex net over the raw text, in English and Korean, that confirms the
two safety flags without asking the model. It only ever sets a flag to True; it
never clears one and never picks a level. `triage.assess` still decides that.

It is a net, not a guarantee: it matches what it recognises and nothing else.
"""

from __future__ import annotations

import re

_NEGATION_BEFORE = re.compile(
    r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bdon'?t\b|\bdoesn'?t\b)[^.!?]{0,14}$",
    re.IGNORECASE,
)
_NEGATION_AFTER_KO = re.compile(r"^[^.!?]{0,8}(?:지 않|지않|않아|않는|없)")

_BREATHING_EN = re.compile(
    r"can'?t breathe|cannot breathe|can not breathe|unable to breathe|not able to breathe"
    r"|trouble breathing|difficulty breathing|hard to breathe|struggling to breathe"
    r"|short(?:ness)? of breath|gasping for (?:air|breath)|can'?t catch my breath",
    re.IGNORECASE,
)
_AIRWAY_EN = re.compile(
    r"throat (?:is |feels? |keeps? |getting |starting to )?(?:clos|swell|swoll|tight)"
    r"|(?:swollen|swelling) (?:throat|tongue)"
    r"|tongue (?:is |feels? |getting )?(?:swell|swoll)"
    r"|(?:lips?|face) (?:is |are |feels? |getting )?(?:swell|swoll)"
    r"|(?:swollen|swelling) (?:lips?|face)",
    re.IGNORECASE,
)
_BREATHING_KO = re.compile(
    r"숨(?:을|이|도)? ?(?:못|안) ?쉬|숨 ?쉬기 ?(?:힘|어렵|곤란)|숨이 ?(?:차|막|가쁘|안)|호흡 ?곤란"
)
_AIRWAY_KO = re.compile(
    r"목이 ?(?:부|붓|조여|막|좁|답답)|혀가 ?(?:부|붓)|입술이 ?(?:부|붓)|얼굴이 ?(?:부|붓)|기도"
)


def _hit(pattern: re.Pattern[str], text: str, *, korean: bool) -> bool:
    for m in pattern.finditer(text):
        before = text[: m.start()]
        after = text[m.end() :]
        if korean:
            if _NEGATION_AFTER_KO.match(after):
                continue
        elif _NEGATION_BEFORE.search(before):
            continue
        return True
    return False


def scan(text: str) -> tuple[bool, bool]:
    """Return (breathing_difficulty, airway_swelling) confirmed by the text."""
    breathing = _hit(_BREATHING_EN, text, korean=False) or _hit(_BREATHING_KO, text, korean=True)
    airway = _hit(_AIRWAY_EN, text, korean=False) or _hit(_AIRWAY_KO, text, korean=True)
    return breathing, airway
