"""The writer's tag, on real MKVs made by ffmpeg: a film's identity set in its
own metadata, what was there kept, and its streams untouched.

The executor's tests file onto `cases.Case.build`'s sparse placeholders,
which hold nothing for mkvpropedit to edit; these, and `test_cli`'s, are
where a tag is made for real.
"""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from reelbarrow import executor
from reelbarrow.analysis.probe import probe
from reelbarrow.executor import Refused, Writer, WriterError, merged_tags

TAGS = {
    "TITLE": "Monte Carlo or Bust!",
    "DATE_RELEASED": "1969-04-28",
    "IMDB": "tt0064688",
    "TMDB": "movie/38792",
}
CHAPTERS = """;FFMETADATA1
[CHAPTER]
TIMEBASE=1/1000
START=0
END=2000
[CHAPTER]
TIMEBASE=1/1000
START=2000
END=4000
"""


@pytest.fixture
def root(tmp_path, ffmpeg, guarded) -> Path:
    """A share holding one film as HandBrake leaves one: chapters, a global
    tag of its own and one per track, and no title."""
    root = tmp_path / "video"
    (root / "import").mkdir(parents=True)
    (tmp_path / "chapters.txt").write_text(CHAPTERS)
    ffmpeg(
        "video/import/film.mkv",
        *("-f", "lavfi", "-i", "testsrc=d=4:s=32x24:r=5"),
        *("-f", "lavfi", "-i", "sine=d=4"),
        *("-i", str(tmp_path / "chapters.txt"), "-map_chapters", "2"),
        *("-map", "0", "-map", "1", "-c:v", "ffv1", "-c:a", "flac"),
        # Global tags already there: one kept, one reelbarrow's replaces.
        *("-metadata", "COMMENT=ripped by ARM", "-metadata", "IMDB=tt0000001"),
    )
    guarded(root)
    return root


def streams(file: Path) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(file), "-map", "0", "-c", "copy"]
        + ["-f", "streamhash", "-hash", "sha256", "-"],
        capture_output=True,
        check=True,
    ).stdout


def tags(file: Path) -> ET.Element:
    out = subprocess.run(
        ["mkvextract", str(file), "tags", "-"], capture_output=True, check=True
    ).stdout
    return ET.fromstring(out.removeprefix(b"\xef\xbb\xbf"))


def track_tags(file: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    return [
        (
            tag.findtext("Targets/TrackUID") or "",
            [(s.findtext("Name"), s.findtext("String")) for s in tag.iter("Simple")],
        )
        for tag in tags(file)
        if tag.find("Targets/TrackUID") is not None
    ]


def test_a_film_is_tagged_with_its_identity_and_nothing_else_changes(root):
    film = root / "import" / "film.mkv"
    before, hashed = probe(film), streams(film)

    detail = Writer(root, dry_run=False).tag("import/film.mkv", TAGS["TITLE"], TAGS)

    after = probe(film)
    assert after.tags["title"] == "Monte Carlo or Bust!"
    for name, value in TAGS.items():
        assert after.tags[f"MOVIE/{name}"] == value
    # What was there is kept, but for the tag reelbarrow sets.
    assert after.tags["COMMENT"] == "ripped by ARM"
    assert "tt0000001" not in after.tags.values()
    assert streams(film) == hashed
    assert after.duration == before.duration
    assert [c.start for c in after.chapters] == [0.0, 2.0]
    assert detail.startswith("kept ")
    assert "COMMENT" in detail and "2 chapters as before" in detail


def test_each_tracks_tags_are_left_alone(root):
    film = root / "import" / "film.mkv"
    before = track_tags(film)
    assert before

    Writer(root, dry_run=False).tag("import/film.mkv", TAGS["TITLE"], TAGS)

    assert track_tags(film) == before


def test_tagging_again_changes_no_tag(root):
    film = root / "import" / "film.mkv"
    writer = Writer(root, dry_run=False)
    writer.tag("import/film.mkv", TAGS["TITLE"], TAGS)
    once = ET.tostring(tags(film))
    writer.tag("import/film.mkv", TAGS["TITLE"], TAGS)
    assert ET.tostring(tags(film)) == once


def test_dry_run_refuses_a_tag_and_the_file_is_unchanged(root):
    film = root / "import" / "film.mkv"
    before = (film.read_bytes(), film.stat().st_mtime_ns)
    with pytest.raises(Refused):
        Writer(root).tag("import/film.mkv", TAGS["TITLE"], TAGS)
    assert (film.read_bytes(), film.stat().st_mtime_ns) == before


def test_a_file_mkvinfo_finds_fault_with_is_not_edited(root):
    """As an interrupted edit can leave one: its segment information's ID
    overwritten, which ffprobe complains of and still exits 0 on."""
    content = (root / "import" / "film.mkv").read_bytes()
    # The ID's first appearance is the seek head's entry for it.
    info = b"\x15\x49\xa9\x66"
    at = content.index(info, content.index(info) + 1)
    broken = content[:at] + bytes(4) + content[at + 4 :]
    (root / "import" / "broken.mkv").write_bytes(broken)
    with pytest.raises(WriterError, match="mkvinfo finds fault"):
        Writer(root, dry_run=False).tag("import/broken.mkv", "x", TAGS)
    assert (root / "import" / "broken.mkv").read_bytes() == broken


def test_a_tag_that_doesnt_read_back_as_set_fails(root, monkeypatch):
    # ffprobe reads the file as it was, before and after.
    first = probe(root / "import" / "film.mkv")
    monkeypatch.setattr(executor, "probe", lambda file: first)
    with pytest.raises(WriterError, match="was edited, but ffprobe doesn't read"):
        Writer(root, dry_run=False).tag("import/film.mkv", TAGS["TITLE"], TAGS)


def test_a_tag_needs_a_file(root):
    with pytest.raises(WriterError, match="isn't a file"):
        Writer(root, dry_run=False).tag("import", "x", TAGS)


# The tags written: what was there, merged with what reelbarrow sets.


def test_merged_tags_keep_globals_and_replace_by_name():
    existing = b"""<?xml version="1.0"?><Tags>
      <Tag><Targets/>
        <Simple><Name>ENCODER</Name><String>Lavf</String></Simple>
        <Simple><Name>title</Name><String>old</String></Simple>
      </Tag>
      <Tag><Targets><TargetTypeValue>50</TargetTypeValue></Targets>
        <Simple><Name>TMDB</Name><String>movie/1</String></Simple>
      </Tag>
      <Tag><Targets><TrackUID>7</TrackUID></Targets>
        <Simple><Name>DURATION</Name><String>00:00:04</String></Simple>
      </Tag>
    </Tags>"""

    kept, document = merged_tags(existing, {"TITLE": "New", "TMDB": "movie/2"})

    assert kept == ["ENCODER"]
    found = ET.fromstring(document)
    # A track's tag isn't global, and is left where it is; a tag emptied by
    # the replacing goes.
    assert [t.findtext("Targets/TrackUID") for t in found] == [None, None]
    first, ours = found
    assert [s.findtext("Name") for s in first.findall("Simple")] == ["ENCODER"]
    assert ours.findtext("Targets/TargetTypeValue") == "50"
    assert ours.findtext("Targets/TargetType") == "MOVIE"
    assert {
        s.findtext("Name"): s.findtext("String") for s in ours.findall("Simple")
    } == {"TITLE": "New", "TMDB": "movie/2"}


def test_merged_tags_of_a_file_with_none():
    kept, document = merged_tags(b"", {"TITLE": "Ünïcode, unfolded"})
    assert kept == []
    (ours,) = ET.fromstring(document)
    assert ours.findtext("Simple/String") == "Ünïcode, unfolded"
