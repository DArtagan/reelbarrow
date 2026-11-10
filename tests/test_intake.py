"""Intake on a tree laid out as the share is: where a job's files are."""

import os
from datetime import UTC, datetime, timedelta

import pytest

from reelbarrow import intake
from reelbarrow.intake import RawFolder, RawFound, RawIndex
from reelbarrow.manifest import Manifest

ARM = "import/automatic-ripping-machine"
START = datetime(2026, 9, 20, 19, 0, 21, tzinfo=UTC)
FINISH = datetime(2026, 9, 20, 21, 48, 45, tzinfo=UTC)


def job(**fields) -> Manifest:
    return Manifest.model_validate(
        {
            "schema": 1,
            "source": "arm",
            "id": "34-178993082181",
            "state": "succeeded",
            "start_time": START.isoformat(),
            "finish_time": FINISH.isoformat(),
            "completed": {"folder": {"path": f"{ARM}/completed/movies/Film (1969)"}},
            **fields,
        }
    )


@pytest.fixture
def share(tmp_path):
    (tmp_path / ARM / "completed/movies/Film (1969)").mkdir(parents=True)
    (tmp_path / ARM / "raw").mkdir()
    return tmp_path


def written(share, path: str, when: datetime) -> None:
    file = share / ARM / "raw" / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"")
    os.utime(file, (when.timestamp(), when.timestamp()))


def test_the_raw_copy_is_the_mkvs_written_while_the_job_ran(share):
    written(share, "Film/B1_t00.mkv", START + timedelta(hours=1))
    # A re-rip of the same disc, the day before: another job's copy.
    written(share, "Film_178000000000/B1_t00.mkv", START - timedelta(days=1))
    written(share, "Other/B1_t00.mkv", FINISH + timedelta(seconds=1))

    location = intake.locate(job(), share, RawIndex(share, f"{ARM}/raw"))

    assert location.raw == (RawFolder(f"{ARM}/raw/Film", RawFound.WRITTEN_DURING_RUN),)
    assert location.completed == f"{ARM}/completed/movies/Film (1969)"
    assert location.missing == ()


def test_the_window_includes_its_ends(share):
    written(share, "AtStart/B1_t00.mkv", START)
    written(share, "AtFinish/B1_t00.mkv", FINISH)
    index = RawIndex(share, f"{ARM}/raw")
    assert index.written_between(START, FINISH) == [
        f"{ARM}/raw/AtFinish",
        f"{ARM}/raw/AtStart",
    ]


def test_only_a_folders_top_level_mkvs_are_looked_at(share):
    # A later DVD's image keeps its MKVs in titles/, and it is recorded.
    written(share, "Image/titles/B1_t00.mkv", START + timedelta(hours=1))
    written(share, "Film/B1_t00.iso", START + timedelta(hours=1))
    written(share, "Loose.mkv", START + timedelta(hours=1))
    location = intake.locate(job(), share, RawIndex(share, f"{ARM}/raw"))
    assert location.raw == ()


def test_a_recorded_raw_folder_is_taken_as_recorded(share):
    written(share, "Recorded/disc.iso", START - timedelta(days=30))
    written(share, "Film/B1_t00.mkv", START + timedelta(hours=1))
    raw = {
        "form": "dvd-image",
        "folder": {"path": f"{ARM}/raw/Recorded"},
        "image": {"path": f"{ARM}/raw/Recorded/disc.iso"},
        "check": {"sizes": "passed", "hashes": "passed"},
        "problems": [],
    }
    location = intake.locate(job(raw=raw), share, RawIndex(share, f"{ARM}/raw"))
    assert location.raw == (RawFolder(f"{ARM}/raw/Recorded", RawFound.RECORDED),)


def test_recorded_folders_not_on_the_share_are_missing(share):
    raw = {
        "form": "mkv-titles",
        "folder": {"path": f"{ARM}/raw/Gone"},
        "check": {"sizes": "passed", "hashes": "passed"},
        "problems": [],
    }
    gone = {"folder": {"path": f"{ARM}/completed/movies/Gone (1969)"}}
    location = intake.locate(
        job(raw=raw, completed=gone), share, RawIndex(share, f"{ARM}/raw")
    )
    assert location.completed is None
    assert location.raw == ()
    assert location.missing == (
        f"{ARM}/completed/movies/Gone (1969)",
        f"{ARM}/raw/Gone",
    )


def test_a_job_still_running_has_no_window(share):
    written(share, "Film/B1_t00.mkv", START + timedelta(hours=1))
    running = job(state="running", finish_time=None)
    assert intake.locate(running, share, RawIndex(share, f"{ARM}/raw")).raw == ()


def test_a_share_without_arms_raw_folder_finds_nothing(tmp_path):
    assert RawIndex(tmp_path, f"{ARM}/raw").written_between(START, FINISH) == []


def test_a_manifest_or_a_folder_of_them(tmp_path):
    for name in ("manifest-arm-2-1.json", "manifest-arm-10-1.json", "notes.txt"):
        (tmp_path / name).write_text("{}")
    assert [p.name for p in intake.manifest_paths(tmp_path)] == [
        "manifest-arm-10-1.json",
        "manifest-arm-2-1.json",
    ]
    one = tmp_path / "manifest-arm-2-1.json"
    assert intake.manifest_paths(one) == [one]


def test_walk_lists_everything_under_a_folder_by_share_path(share):
    top = share / ARM / "completed/movies/Film (1969)"
    (top / "extras").mkdir()
    (top / "extras/title_2.mkv").write_bytes(b"x")
    (top / "Film (1969).mkv").write_bytes(b"xy")
    entries = [
        (path, is_folder)
        for path, _, is_folder in intake.walk(
            share, f"{ARM}/completed/movies/Film (1969)"
        )
    ]
    assert entries == [
        (f"{ARM}/completed/movies/Film (1969)/extras", True),
        (f"{ARM}/completed/movies/Film (1969)/Film (1969).mkv", False),
        (f"{ARM}/completed/movies/Film (1969)/extras/title_2.mkv", False),
    ]
