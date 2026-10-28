import pytest

from reelbarrow.analysis.dvd import DvdTitle, dvd_structure, parse_lsdvd
from reelbarrow.analysis.segments import Segment
from reelbarrow.analysis.tools import AnalysisError

NTSC = 1001 / 1000


def title(disc_title, vts, chapters, cells):
    """A title of the synthetic image, from the IFO's lengths and sectors."""
    return DvdTitle(
        disc_title=disc_title,
        vts=vts,
        fps=29.97,
        duration=sum(chapters) * NTSC,
        chapters=tuple(c * NTSC for c in chapters),
        cells=tuple(
            Segment(vts, start, end, length * NTSC)
            for (start, end), length in zip(cells, chapters, strict=True)
        ),
    )


# tests/fixtures/dvd/make.sh authors these: 20 s, 45 s and 8 s of 29.97 fps
# video, which the IFO lists as 20.000, 44.967 and 8.000 of its 30-frame seconds.
TITLES = (
    title(1, 1, (4.8, 5.4, 4.8, 5.0), ((0, 341), (341, 691), (691, 971), (971, 1269))),
    title(
        2,
        1,
        (10.2, 9.6, 10.2, 10.2, 4.767),
        ((1269, 1960), (1960, 2503), (2503, 3059), (3059, 3614), (3614, 3893)),
    ),
    title(3, 2, (8.0,), ((0, 581),)),
)


def assert_titles(actual):
    assert len(actual) == len(TITLES)
    for got, want in zip(actual, TITLES, strict=True):
        assert (got.disc_title, got.vts, got.fps) == (
            want.disc_title,
            want.vts,
            want.fps,
        )
        assert got.duration == pytest.approx(want.duration, abs=0.001)
        assert got.chapters == pytest.approx(want.chapters, abs=0.001)
        assert [(c.source, c.start, c.end) for c in got.cells] == [
            (c.source, c.start, c.end) for c in want.cells
        ]
        assert [c.seconds for c in got.cells] == pytest.approx(
            [c.seconds for c in want.cells], abs=0.001
        )


def test_an_image(fixtures):
    structure = dvd_structure(fixtures / "dvd/synthetic.iso")
    assert structure.label == "SYNTHETIC_DVD"
    assert_titles(structure.titles)


def test_a_directory(fixtures):
    structure = dvd_structure(fixtures / "dvd")
    assert structure.label is None
    assert_titles(structure.titles)


def test_the_images_lsdvd(fixtures):
    # `lsdvd -c -d -v -Oy synthetic.iso` from Debian's lsdvd 0.20, which the
    # image installs. It quotes and punctuates differently from the devenv's
    # 0.17, and adds the disc ID.
    structure = parse_lsdvd((fixtures / "dvd/lsdvd-0.20.txt").read_text())
    assert structure.label == "SYNTHETIC_DVD"
    assert_titles(structure.titles)


def test_chapter_starts():
    assert TITLES[0].chapter_starts == pytest.approx(
        (0.0, 4.8 * NTSC, 10.2 * NTSC, 15.0 * NTSC)
    )


def lsdvd(
    *, device="disc.iso", label="DISC", provider="", fps="29.97", chapters="20.000"
):
    return f"""libdvdread: Encrypted DVD support unavailable.
lsdvd = {{
  'device' : '{device}',
  'title' : '{label}',
  'vmg_id' : 'DVDVIDEO-VMG',
  'provider_id' : "{provider}",
  'track' : [
    {{
      'ix' : 1,
      'length' : 20.000,
      'vts_id' : 'DVDVIDEO-VTS',
      'vts' : 1,
      'ttn' : 1,
      'fps' : {fps},
      'format' : 'NTSC',
      'chapter' : [
        {{
          'ix' : 1,
          'length' : {chapters},
          'startcell' : 1,
        }},
      ],
      'cell' : [
        {{
          'ix' : 1,
          'length' : 20.000,
          'first_sector' : 0,
          'last_sector' : 99,
        }},
      ],
    }},
  ],
  'longest_track' : 1,
}}
"""


def test_quotes_in_free_text_are_read_as_text():
    # lsdvd copies these in unescaped. A legacy library file is named for its
    # film, apostrophes and all.
    structure = parse_lsdvd(
        lsdvd(
            device="/video/movies/Ocean's Eleven (2001)/Ocean's Eleven (2001).iso",
            label="OCEAN'S_11', 'track' : [], 'x' : '",
            provider='Studio "A"',
        )
    )
    assert structure.label == "OCEAN'S_11', 'track' : [], 'x' : '"
    assert [t.disc_title for t in structure.titles] == [1]


def test_pal_is_not_scaled():
    (only,) = parse_lsdvd(lsdvd(fps="25.00")).titles
    assert only.duration == 20.0
    assert only.cells == (Segment(1, 0, 100, 20.0),)


def test_an_unknown_frame_rate_is_refused():
    with pytest.raises(AnalysisError, match="frame rate"):
        parse_lsdvd(lsdvd(fps="-1.0"))


def test_chapters_that_do_not_add_up_are_refused():
    with pytest.raises(AnalysisError, match="chapters sum"):
        parse_lsdvd(lsdvd(chapters="12.000"))


def test_not_lsdvd_output():
    with pytest.raises(AnalysisError, match="not understood"):
        parse_lsdvd("Disc Title: SYNTHETIC_DVD\n")


def test_not_a_dvd(tmp_path):
    with pytest.raises(AnalysisError, match="lsdvd"):
        dvd_structure(tmp_path / "absent.iso")
