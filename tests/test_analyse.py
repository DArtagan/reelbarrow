"""`reelbarrow analyse` on a tree laid out as the share is."""

import os
from datetime import UTC, datetime, timedelta

import pytest

from reelbarrow.analyse import Analysis, analyse
from reelbarrow.intake import RawFound, RawIndex
from reelbarrow.manifest import Manifest

ARM = "import/automatic-ripping-machine"
START = datetime(2026, 9, 20, 19, 0, 21, tzinfo=UTC)
FINISH = datetime(2026, 9, 20, 21, 48, 45, tzinfo=UTC)
COMPLETED = f"{ARM}/completed/movies/Film (1969)"


@pytest.fixture
def chapters(tmp_path):
    path = tmp_path / "chapters.txt"
    path.write_text(
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=4000\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=4000\nEND=10000\n"
    )
    return path


@pytest.fixture
def share(tmp_path, ffmpeg, chapters):
    root = tmp_path / "video"
    film = ffmpeg(
        "film.mkv",
        *("-f", "lavfi", "-i", "testsrc=d=10:s=64x48:r=10"),
        *("-i", str(chapters), "-map", "0", "-map_chapters", "1", "-c:v", "ffv1"),
    )
    (root / COMPLETED / "extras").mkdir(parents=True)
    film.rename(root / COMPLETED / "Film (1969).mkv")
    (root / COMPLETED / "notes.txt").write_text("not a video")
    (root / COMPLETED / "extras" / "title_2.mkv").write_bytes(b"not matroska")
    raw = root / ARM / "raw" / "Film"
    raw.mkdir(parents=True)
    copy = raw / "B1_t00.mkv"
    copy.write_bytes((root / COMPLETED / "Film (1969).mkv").read_bytes())
    during = (START + timedelta(hours=1)).timestamp()
    os.utime(copy, (during, during))
    return root


def job() -> Manifest:
    return Manifest.model_validate(
        {
            "schema": 1,
            "source": "arm",
            "id": "34-178993082181",
            "state": "succeeded",
            "start_time": START.isoformat(),
            "finish_time": FINISH.isoformat(),
            "completed": {"folder": {"path": COMPLETED}},
        }
    )


def test_every_file_is_listed_and_every_video_measured(share):
    document = analyse(job(), share, RawIndex(share, f"{ARM}/raw"))

    completed = document.completed
    assert completed.path == COMPLETED
    assert [f.path for f in completed.folders] == [f"{COMPLETED}/extras"]
    files = {f.path.removeprefix(f"{COMPLETED}/"): f for f in completed.files}
    assert sorted(files) == ["Film (1969).mkv", "extras/title_2.mkv", "notes.txt"]
    film = files["Film (1969).mkv"]
    assert film.video.duration == pytest.approx(10, abs=0.1)
    assert film.video.chapters == [0.0, 4.0]
    assert film.size == (share / COMPLETED / "Film (1969).mkv").stat().st_size
    assert files["notes.txt"].video is None and files["notes.txt"].error is None
    # A video that can't be measured says so, rather than stopping the job.
    assert files["extras/title_2.mkv"].video is None
    assert "ffprobe" in files["extras/title_2.mkv"].error


def test_the_raw_copy_found_is_measured_and_says_how_it_was_found(share):
    document = analyse(job(), share, RawIndex(share, f"{ARM}/raw"))

    (raw,) = document.raw
    assert raw.path == f"{ARM}/raw/Film"
    assert raw.found is RawFound.WRITTEN_DURING_RUN
    (copy,) = raw.files
    assert copy.mtime == START + timedelta(hours=1)
    assert copy.video.chapters == [0.0, 4.0]


def test_the_document_reads_back_as_written(share):
    document = analyse(job(), share, RawIndex(share, f"{ARM}/raw"))
    assert Analysis.model_validate(document.to_json()) == document
    assert document.to_json()["schema"] == 1


def test_a_missing_completed_folder_is_reported_not_raised(tmp_path):
    document = analyse(job(), tmp_path, RawIndex(tmp_path, f"{ARM}/raw"))
    assert document.completed is None
    assert document.missing == [COMPLETED]
