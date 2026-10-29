"""Where the audio of one title is found inside another's.

The shorter fingerprint is cut into 15-second windows. Each window votes for
the offset into the longer at which its frames recur, and the winning offset is
kept if more than MATCH of the bits there agree. A second cut
of a film matches at a rising offset; another film matches nowhere.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from reelbarrow.analysis.fingerprint import FRAME_SECONDS

WINDOW = int(15 / FRAME_SECONDS)
MATCH = 0.75
# Frames are looked up by their top 20 bits, so a frame still votes where it
# differs from the longer's only in the low bits.
INDEX_SHIFT = 12


@dataclass(frozen=True, slots=True)
class Window:
    # First frame of the window in the shorter fingerprint.
    start: int
    # Frames to add to reach the same audio in the longer, or None when no
    # frame of the window recurs there at all.
    offset: int | None
    # Fraction of bits equal at that offset.
    similarity: float

    @property
    def matched(self) -> bool:
        return self.offset is not None and self.similarity > MATCH


@dataclass(frozen=True, slots=True)
class Alignment:
    # Which argument was the shorter, and so was windowed.
    shorter: Literal["a", "b"]
    # Frames in the shorter.
    length: int
    windows: tuple[Window, ...]

    @property
    def coverage(self) -> float:
        """Share of the shorter found in the longer."""
        matched = sum(WINDOW for w in self.windows if w.matched)
        return matched / self.length if self.length else 0.0


def align(a: Sequence[int], b: Sequence[int]) -> Alignment:
    if len(a) <= len(b):
        shorter, query, reference = "a", a, b
    else:
        shorter, query, reference = "b", b, a

    index: dict[int, list[int]] = {}
    for i, frame in enumerate(reference):
        index.setdefault(frame >> INDEX_SHIFT, []).append(i)

    windows = []
    # A final partial window is not scored, as in the measurements.
    for start in range(0, len(query) - WINDOW, WINDOW):
        votes: dict[int, int] = {}
        for k in range(start, start + WINDOW):
            for i in index.get(query[k] >> INDEX_SHIFT, ()):
                votes[i - k] = votes.get(i - k, 0) + 1
        if not votes:
            windows.append(Window(start, None, 0.0))
            continue
        offset = max(votes, key=votes.__getitem__)
        at = start + offset
        if 0 <= at < len(reference):
            score = _similarity(
                query[start : start + WINDOW], reference[at : at + WINDOW]
            )
        else:
            score = 0.0
        windows.append(Window(start, offset, score))

    return Alignment(shorter, len(query), tuple(windows))


def _similarity(a: Sequence[int], b: Sequence[int]) -> float:
    # Divided by the full window even when the longer runs out first, so a
    # window hanging off its end scores low.
    differing = sum((x ^ y).bit_count() for x, y in zip(a, b, strict=False))
    return 1 - differing / (32 * WINDOW)
