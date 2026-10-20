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
        # Two cuts of one film, Robin Hood job 35.
        ("robinhood-140", "robinhood-155", 94.9),
        # Two films on one disc, The Rescuers job 27.
        ("rescuers-title71", "rescuers-feature", 0.0),
        # Unrelated films. The 0.3% is one window: the Rescuers feature's
        # silent first 15 s matches the silence at the end of either cut.
        ("robinhood-155", "rescuers-title71", 0.0),
        ("robinhood-140", "rescuers-title71", 0.0),
        ("rescuers-feature", "robinhood-155", 0.3),
        ("rescuers-feature", "robinhood-140", 0.3),
    ],
)
def test_the_measured_table(fingerprints, a, b, percent):
    assert coverage(fingerprints, a, b) == percent
    assert coverage(fingerprints, b, a) == percent


def test_the_shorter_is_windowed_whichever_comes_first(fingerprints):
    short = fingerprints["robinhood-140"].frames
    long = fingerprints["robinhood-155"].frames
    assert align(short, long).shorter == "a"
    assert align(long, short).shorter == "b"
    assert align(long, short).length == len(short)


def test_a_longer_cut_shows_as_a_rising_offset(fingerprints):
    result = align(
        fingerprints["robinhood-140"].frames, fingerprints["robinhood-155"].frames
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
