"""Names the share can hold, made from names metadata providers give.

Library names are ASCII (Will, 2026-11-10). The fileserver's Samba runs `unix
charset = ISO-8859-1`, so a name holding any character above U+00FF fails with
EIO, which reads as a broken disk rather than a bad name. Latin-1 would get
past that, but each such name is one the filename-charset migration then has
to convert and repair in Plex's database, and `media/video` held no non-ASCII
name at all when the migration was measured (0 of 51,876, 2026-09-02). ASCII
is the same bytes in either charset, so the migration never touches a name
made here. Plex shows its agent's title and matches by `{tmdb-N}`, and
`movie.nfo` keeps TMDB's own, so only the name on disk loses its accents.

The characters Windows clients can't open are replaced the way the library's
2024 entries were filed (`Thor - Ragnarok (2017) {tmdb-284053}`).
"""

import unicodedata

ASCII_END = 0x80

# Punctuation providers emit, and letters that have no decomposition to an
# ASCII base and would otherwise vanish.
_SPELLED = str.maketrans(
    {
        "\N{HYPHEN}": "-",
        "\N{NON-BREAKING HYPHEN}": "-",
        "\N{FIGURE DASH}": "-",
        "\N{EN DASH}": "-",
        "\N{EM DASH}": "-",
        "\N{HORIZONTAL BAR}": "-",
        "\N{LEFT SINGLE QUOTATION MARK}": "'",
        "\N{RIGHT SINGLE QUOTATION MARK}": "'",
        "\N{SINGLE LOW-9 QUOTATION MARK}": "'",
        "\N{SINGLE HIGH-REVERSED-9 QUOTATION MARK}": "'",
        "\N{LEFT DOUBLE QUOTATION MARK}": '"',
        "\N{RIGHT DOUBLE QUOTATION MARK}": '"',
        "\N{DOUBLE LOW-9 QUOTATION MARK}": '"',
        "\N{HORIZONTAL ELLIPSIS}": "...",
        "\N{PRIME}": "'",
        "\N{DOUBLE PRIME}": '"',
        "\N{NO-BREAK SPACE}": " ",
        "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}": '"',
        "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}": '"',
        "\N{MULTIPLICATION SIGN}": "x",
        "\N{LATIN CAPITAL LETTER AE}": "AE",
        "\N{LATIN SMALL LETTER AE}": "ae",
        "\N{LATIN CAPITAL LIGATURE OE}": "OE",
        "\N{LATIN SMALL LIGATURE OE}": "oe",
        "\N{LATIN CAPITAL LETTER O WITH STROKE}": "O",
        "\N{LATIN SMALL LETTER O WITH STROKE}": "o",
        "\N{LATIN SMALL LETTER SHARP S}": "ss",
        "\N{LATIN CAPITAL LETTER L WITH STROKE}": "L",
        "\N{LATIN SMALL LETTER L WITH STROKE}": "l",
        "\N{LATIN CAPITAL LETTER D WITH STROKE}": "D",
        "\N{LATIN SMALL LETTER D WITH STROKE}": "d",
        "\N{LATIN CAPITAL LETTER ETH}": "D",
        "\N{LATIN SMALL LETTER ETH}": "d",
        "\N{LATIN CAPITAL LETTER THORN}": "Th",
        "\N{LATIN SMALL LETTER THORN}": "th",
        "\N{LATIN SMALL LETTER DOTLESS I}": "i",
    }
)

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

# A name component's limit on the share's filesystem, in bytes.
MAX_BYTES = 255


class UnwritableName(ValueError):
    """No name the share can hold is left of it."""


def to_ascii(text: str) -> str:
    """Each character as ASCII: spelled out, or its base letter, or dropped."""
    out = []
    for ch in text.translate(_SPELLED):
        if ord(ch) < ASCII_END:
            out.append(ch)
            continue
        # NFKD first, so an accented letter keeps its base rather than
        # vanishing; then drop what still has no ASCII form.
        decomposed = unicodedata.normalize("NFKD", ch)
        out.append("".join(c for c in decomposed if ord(c) < ASCII_END))
    return "".join(out)


def fold(text: str) -> str:
    """A provider's name, as the share and its clients can write it."""
    name = to_ascii(text).replace(": ", " - ")
    name = "".join(_UNSAFE.get(ch, ch) for ch in name if ord(ch) >= 0x20)
    return " ".join(name.split())


def component(text: str) -> str:
    """One whole path component, for the library."""
    name = fold(text)
    # Windows drops a trailing dot or space, so two names would meet as one.
    name = name.rstrip(". ")
    if not name or name in (".", ".."):
        raise UnwritableName(f"nothing of {text!r} can be written to the share")
    if len(name) > MAX_BYTES:
        raise UnwritableName(f"{name!r} is longer than the share allows")
    return name
