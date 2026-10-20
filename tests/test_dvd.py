import pytest

from reelbarrow.analysis.dvd import DvdTitle, dvd_structure, parse_lsdvd
from reelbarrow.analysis.tools import AnalysisError

# tests/fixtures/dvd/make.sh authors these.
TITLES = (
    DvdTitle(1, 20.0, (4.8, 5.4, 4.8, 5.0)),
    DvdTitle(2, 44.967, (10.2, 9.6, 10.2, 10.2, 4.767)),
    DvdTitle(3, 8.0, (8.0,)),
)


def test_an_image(fixtures):
    structure = dvd_structure(fixtures / "dvd/synthetic.iso")
    assert structure.label == "SYNTHETIC_DVD"
    assert structure.titles == TITLES


def test_a_directory(fixtures):
    structure = dvd_structure(fixtures / "dvd")
    assert structure.label is None
    assert structure.titles == TITLES


def test_the_images_lsdvd(fixtures):
    # `lsdvd -c synthetic.iso` from Debian's lsdvd 0.20, which the image
    # installs. It adds a disc ID line to what the devenv's 0.17 prints.
    structure = parse_lsdvd((fixtures / "dvd/lsdvd-0.20.txt").read_text())
    assert structure.label == "SYNTHETIC_DVD"
    assert structure.titles == TITLES


def test_a_chapter_count_mismatch_is_refused():
    with pytest.raises(AnalysisError, match="chapters"):
        parse_lsdvd(
            "Disc Title: unknown\n"
            "Title: 01, Length: 00:00:20.000 Chapters: 02, Cells: 02,"
            " Audio streams: 01, Subpictures: 00\n"
            "\tChapter: 01, Length: 00:00:20.000, Start Cell: 01\n"
        )


def test_not_a_dvd(tmp_path):
    with pytest.raises(AnalysisError, match="lsdvd"):
        dvd_structure(tmp_path / "absent.iso")
