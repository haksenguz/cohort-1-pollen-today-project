"""A conversation title, taken from the user's own words.

The history list shows a title instead of "Untitled conversation", so a title
has to exist from the first turn. It is derived rather than generated: a model
call would cost money and add latency to every turn, and a title the user did
not write is a title they cannot recognise.

The rules are few on purpose. The text is the user's own, the whitespace is
collapsed, the cut lands on a word boundary, and the language is whatever the
user wrote in.
"""

# A title is a list preview, not a summary. Sixty characters fit on one line
# of a phone-sized history row.
MAX_TITLE_LENGTH = 60

# What a cut title ends with. One glyph, so it never reads as a sentence that
# was cut short by a mistake.
ELLIPSIS = "…"


def derive_title(message: str, *, max_length: int = MAX_TITLE_LENGTH) -> str | None:
    """A title for a conversation, taken from the user's first message.

    Returns None when the message holds no words, because there is no title to
    be had out of whitespace.

    The cut lands on a word boundary where there is one to land on, so a title
    never ends in half a word.
    """
    collapsed = " ".join(message.split())
    if not collapsed:
        return None
    if len(collapsed) <= max_length:
        return collapsed

    head = collapsed[:max_length]
    boundary = head.rfind(" ")
    if boundary > 0:
        head = head[:boundary]
    return f"{head.rstrip()}{ELLIPSIS}"
