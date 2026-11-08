from itertools import pairwise

import pytest

from reelbarrow.analysis.alignment import align
from reelbarrow.analysis.fingerprint import FRAME_SECONDS


def coverage(fingerprints, a, b) -> float:
    return round(
        100 * align(fingerprints[a].frames, fingerprints[b].frames).coverage, 1
    )


@pytest.mark.parametrize(
    ("a", "b", "percent"),
    [
        # Two cuts of one film.
        ("robin-hood-theatrical", "robin-hood-directors-cut", 94.9),
        # Two films on one disc.
        ("rescuers-down-under", "rescuers", 0.0),
        # Unrelated films. The 0.3% is one window: The Rescuers'
        # silent first 15 s matches the silence at the end of either cut.
        ("robin-hood-directors-cut", "rescuers-down-under", 0.0),
        ("robin-hood-theatrical", "rescuers-down-under", 0.0),
        ("rescuers", "robin-hood-directors-cut", 0.3),
        ("rescuers", "robin-hood-theatrical", 0.3),
    ],
)
def test_the_measured_table(fingerprints, a, b, percent):
    assert coverage(fingerprints, a, b) == percent
    assert coverage(fingerprints, b, a) == percent


def test_the_shorter_is_windowed_whichever_comes_first(fingerprints):
    short = fingerprints["robin-hood-theatrical"].frames
    long = fingerprints["robin-hood-directors-cut"].frames
    assert align(short, long).shorter == "a"
    assert align(long, short).shorter == "b"
    assert align(long, short).length == len(short)


def test_a_longer_cut_shows_as_a_rising_offset(fingerprints):
    result = align(
        fingerprints["robin-hood-theatrical"].frames,
        fingerprints["robin-hood-directors-cut"].frames,
    )
    minutes = [w.offset * FRAME_SECONDS / 60 for w in result.windows if w.matched]

    # In step at the start, 15.5 minutes of inserted material behind by the end.
    assert minutes[0] == pytest.approx(0, abs=0.05)
    assert minutes[-1] == pytest.approx(15.5, abs=0.1)
    steps = list(pairwise(minutes))
    forward = [s for s in steps if s[1] > s[0] + 0.05]
    back = [s for s in steps if s[1] < s[0] - 0.05]
    # The inserted passages, and the few scenes the longer cut reorders.
    assert len(forward) > 4 * len(back)
    assert 1 <= len(back) <= 5
