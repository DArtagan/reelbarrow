import pytest

from reelbarrow.analysis.segments import Segment, covered, own, span, units


def play(*pieces):
    """A title from (source, start, end) pieces, one unit to the second."""
    return tuple(
        Segment(source, start, end, float(end - start)) for source, start, end in pieces
    )


# A series disc's shape, as Pinky and the Brain D2's: three episodes in one
# title set, each closing on a short cell they share, and a play-all that plays
# each episode's own cells in turn and the shared one once, at the end.
CLOSING = (1, 300, 302)
EPISODES = (
    play((1, 0, 100), CLOSING),
    play((1, 100, 200), CLOSING),
    play((1, 200, 300), CLOSING),
)
PLAY_ALL = play((1, 0, 100), (1, 100, 200), (1, 200, 300), CLOSING)


def test_units():
    assert units(PLAY_ALL) == 302
    assert units(()) == 0


def test_each_episode_is_inside_the_play_all():
    for episode in EPISODES:
        assert covered(episode, [PLAY_ALL]) == units(episode)


def test_the_episodes_play_the_whole_play_all():
    assert covered(PLAY_ALL, EPISODES) == units(PLAY_ALL)


def test_episodes_overlap_only_by_their_shared_cell():
    assert covered(EPISODES[0], [EPISODES[1]]) == 2


def test_overlapping_others_are_counted_once():
    # Two others covering 10-60 and 40-90 between them play 10-90 of 0-100.
    assert covered(play((1, 0, 100)), [play((1, 10, 60)), play((1, 40, 90))]) == 80
    # Nested inside another, an other adds nothing.
    assert covered(play((1, 0, 100)), [play((1, 10, 90)), play((1, 20, 30))]) == 80


def test_another_source_plays_nothing_of_it():
    # Sector 0 of title set 2 is not sector 0 of title set 1, nor clip "00001".
    assert covered(play((1, 0, 100)), [play((2, 0, 100)), play(("00001", 0, 100))]) == 0


def test_own_is_what_no_other_plays():
    assert own(EPISODES[1], [EPISODES[0], EPISODES[2]]) == play((1, 100, 200))
    assert own(play((1, 0, 100)), [play((1, 20, 30)), play((1, 25, 50))]) == play(
        (1, 0, 20), (1, 50, 100)
    )
    assert own(EPISODES[0], [EPISODES[0]]) == ()


def test_own_keeps_a_cut_cells_rate():
    # A cell's seconds are shared out over its sectors.
    (left,) = own((Segment(1, 0, 100, 50.0),), [play((1, 40, 100))])
    assert left == Segment(1, 0, 40, 20.0)


def test_span_is_where_the_whole_plays_the_part():
    starts = [
        span(own(e, [o for o in EPISODES if o is not e]), PLAY_ALL) for e in EPISODES
    ]
    assert starts == [(0.0, 100.0), (100.0, 200.0), (200.0, 300.0)]
    # The shared cell is played by the whole at its end, so each episode taken
    # whole reaches there.
    assert span(EPISODES[0], PLAY_ALL) == (0.0, 302.0)


def test_span_in_seconds_not_units():
    whole = (Segment("00001", 0, 4500, 0.1), Segment("00002", 0, 90000, 2.0))
    part = (Segment("00002", 45000, 90000, 1.0),)
    assert span(part, whole) == pytest.approx((1.1, 2.1))


def test_span_of_nothing_shared():
    assert span(play((2, 0, 10)), PLAY_ALL) is None
