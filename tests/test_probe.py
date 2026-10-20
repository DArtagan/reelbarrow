import json

import pytest

from reelbarrow.analysis.probe import parse_probe, probe
from reelbarrow.analysis.tools import AnalysisError


def test_arm_transcode(fixtures):
    # ffprobe of ARM's 140.5-minute Robin Hood cut, job 35.
    raw = json.loads((fixtures / "probe/robinhood-140.json").read_text())
    probed = parse_probe(raw)

    assert probed.format_name == "matroska,webm"
    assert probed.duration == pytest.approx(8430.801)
    assert [s.codec_name for s in probed.of_type("audio")] == ["opus"] * 5
    # Matroska gives audio durations only as a tag.
    first = probed.of_type("audio")[0]
    assert (first.index, first.channels, first.language) == (1, 2, "eng")
    assert first.duration == pytest.approx(8430.801)
    assert len(probed.chapters) == 20
    assert probed.chapters[0].end == pytest.approx(690.33)
    assert probed.chapters[0].title == "Chapter 1"
    assert probed.raw is raw


def test_probe_reads_streams_and_chapters(ffmpeg, tmp_path):
    chapters = tmp_path / "chapters.txt"
    chapters.write_text(
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=4000\ntitle=Opening\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=4000\nEND=10000\ntitle=Rest\n"
    )
    path = ffmpeg(
        "probe.mkv",
        *("-f", "lavfi", "-i", "testsrc=d=10:s=64x48:r=10"),
        *("-f", "lavfi", "-i", "sine=f=440:d=10"),
        *("-f", "lavfi", "-i", "sine=f=660:d=10"),
        *("-i", str(chapters)),
        *("-map", "0", "-map", "1", "-map", "2", "-map_chapters", "3"),
        *("-c:v", "ffv1", "-c:a", "flac", "-ac:a:1", "2"),
        *("-metadata:s:a:0", "language=eng", "-metadata:s:a:1", "title=Commentary"),
    )
    probed = probe(path)

    assert [s.codec_type for s in probed.streams] == ["video", "audio", "audio"]
    audio = probed.of_type("audio")
    assert [s.channels for s in audio] == [1, 2]
    assert audio[0].language == "eng"
    assert audio[1].title == "Commentary"
    assert all(s.duration == pytest.approx(10, abs=0.1) for s in probed.streams)
    assert [(c.start, c.end, c.title) for c in probed.chapters] == [
        (0, 4, "Opening"),
        (4, 10, "Rest"),
    ]


def test_probe_of_a_missing_file_fails(tmp_path):
    with pytest.raises(AnalysisError, match="ffprobe"):
        probe(tmp_path / "absent.mkv")


def test_output_without_a_format_is_refused():
    with pytest.raises(AnalysisError):
        parse_probe({"streams": []})
