"""Names the share can hold, made from names metadata providers give.

The fileserver's Samba runs `unix charset = ISO-8859-1`, so any path holding a
character above U+00FF fails with EIO, which reads as a broken disk rather than
a bad name. Until the deployment's filename-charset migration lands, a name is
folded exactly as the deployment's ARM title hook (`arm-title-charset.py`)
folds ARM's: the punctuation providers emit is mapped, the rest decomposed,
and whatever has no Latin-1 form dropped. Latin-1 rather than ASCII, as the
share takes it and the library already holds `Mànran` under a Latin-1 name.

Then the characters Windows clients can't open are replaced the way the
library's 2024 entries were filed (`Thor - Ragnarok (2017) {tmdb-284053}`).
"""

import unicodedata

LATIN1_END = 0x100

# The hook's map, character for character.
_PROVIDER_PUNCTUATION = {
    0x2010: "-",
    0x2011: "-",
    0x2012: "-",
    0x2013: "-",
    0x2014: "-",
    0x2015: "-",
    0x2018: "'",
    0x2019: "'",
    0x201A: "'",
    0x201B: "'",
    0x201C: '"',
    0x201D: '"',
    0x201E: '"',
    0x2026: "...",
    0x2032: "'",
    0x2033: '"',
    0x00A0: " ",
}

# What SMB refuses from a Windows client, after ": " has become " - ".
_UNSAFE = {
    ":": "-",
    "/": "-",
    "\\": "-",
    '"': "'",
    "*": "",
    "?": "",
    "<": "",
    ">": "",
    "|": "",
}

# A name component's limit on the share's filesystem, in bytes of its charset.
MAX_BYTES = 255


class UnwritableName(ValueError):
    """No name the share can hold is left of it."""


def latin1(text: str) -> str:
    """The deployment's ARM title hook, as it folds a title."""
    out = []
    for ch in text.translate(_PROVIDER_PUNCTUATION):
        if ord(ch) < LATIN1_END:
            out.append(ch)
            continue
        # NFKD first, so an accented character keeps its base letter rather
        # than vanishing entirely; then drop what still has no Latin-1 form.
        decomposed = unicodedata.normalize("NFKD", ch)
        out.append("".join(c for c in decomposed if ord(c) < LATIN1_END))
    return "".join(out)


def fold(text: str) -> str:
    """A provider's name, as the share and its clients can write it."""
    name = latin1(text).replace(": ", " - ")
    name = "".join(_UNSAFE.get(ch, ch) for ch in name if ord(ch) >= 0x20)
    return " ".join(name.split())


def component(text: str) -> str:
    """One whole path component, for the library."""
    name = fold(text)
    # Windows drops a trailing dot or space, so two names would meet as one.
    name = name.rstrip(". ")
    if not name or name in (".", ".."):
        raise UnwritableName(f"nothing of {text!r} can be written to the share")
    if len(name.encode("latin-1")) > MAX_BYTES:
        raise UnwritableName(f"{name!r} is longer than the share allows")
    return name
