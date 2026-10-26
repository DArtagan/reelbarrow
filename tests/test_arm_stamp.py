"""The raw folder's stamp, as the deployment's ARM writes it.

Each fixture is a real `arm-job.json`, copied from a raw folder. The tests pin
the rules *The raw folder's stamp* in the design states, so a stamp that breaks
the contract fails here before any reader is built on it. A change to the stamp
comes with a fixture here.

- job 76: a DVD, its title map written after the fact
- job 77: a DVD, its title map written by the job
- job 78: a Blu-ray movie
- job 80: a Blu-ray series disc from before `duplicates`
- job 82: a Blu-ray whose structure couldn't be read, so no `duplicates`
- job 83: a Blu-ray series disc whose play-all was skipped
"""

import json
from pathlib import Path

import pytest

STAMPS = Path(__file__).parent / "fixtures" / "stamps"
FIXTURES = sorted(STAMPS.glob("job-*.json"))
BASE = {
    "schema",
    "job_id",
    "label",
    "disctype",
    "crc_id",
    "stage",
    "start_time",
    "complete",
    "problems",
    "titles",
}


def load(name: str) -> dict:
    return json.loads((STAMPS / name).read_text())


@pytest.fixture(params=FIXTURES, ids=lambda p: p.stem)
def stamp(request: pytest.FixtureRequest) -> dict:
    return json.loads(request.param.read_text())


def test_every_job_named_in_the_docstring_has_a_fixture():
    assert [p.stem for p in FIXTURES] == [f"job-{n}" for n in (76, 77, 78, 80, 82, 83)]


def test_schema_one_holds_the_base_fields(stamp):
    assert stamp["schema"] == 1
    assert set(stamp) >= BASE
    assert isinstance(stamp["job_id"], int)


def test_complete_agrees_with_its_problems(stamp):
    assert stamp["complete"] in (True, False, None)
    assert (stamp["complete"] is False) == bool(stamp["problems"])


def test_a_dvd_has_a_crc_and_a_blu_ray_neither_crc_nor_title_map(stamp):
    if stamp["disctype"] == "dvd":
        assert isinstance(stamp["crc_id"], str)
    else:
        assert stamp["disctype"] == "bluray"
        assert stamp["crc_id"] is None
        assert stamp["titles"] is None


def test_a_title_map_gives_each_transcode_one_disc_title(stamp):
    if not stamp["titles"]:
        pytest.skip("no title map")
    numbers = [t["handbrake_title"] for t in stamp["titles"] if t["handbrake_title"]]
    assert len(numbers) == len(set(numbers))
    for title in stamp["titles"]:
        assert isinstance(title["disc_title"], int)
        assert title["mkv"].endswith(".mkv")


def test_duplicates_skip_only_what_a_whole_accounts_for(stamp):
    if "duplicates" not in stamp:
        pytest.skip("predates duplicates, or its structure couldn't be read")
    duplicates = stamp["duplicates"]
    source = "playlist" if stamp["disctype"] == "bluray" else "disc_title"
    explained = set()
    for whole in duplicates["wholes"]:
        assert whole["kept"] in ("parts", "whole", "both")
        assert len(whole["parts"]) >= 2
        assert source in whole
        starts = [part["start"] for part in whole["parts"]]
        assert starts == sorted(starts)
        if whole["kept"] == "parts":
            explained.add(whole["title"])
        elif whole["kept"] == "whole":
            explained.update(part["title"] for part in whole["parts"])
    for skipped in duplicates["skipped"]:
        assert source in skipped
        assert skipped["reason"]
    assert {s["title"] for s in duplicates["skipped"]} <= explained


def test_a_series_play_all_is_skipped_and_its_episodes_placed():
    duplicates = load("job-83.json")["duplicates"]
    assert [s["title"] for s in duplicates["skipped"]] == [7]
    (whole,) = duplicates["wholes"]
    assert (whole["title"], whole["kept"], whole["interleaved"]) == (7, "parts", False)
    assert [p["title"] for p in whole["parts"]] == [2, 3, 4]
    assert [p["start"] for p in whole["parts"]] == [0.0, 2859.79, 5658.62]


def test_a_missing_field_reads_as_not_recorded():
    # Jobs 80 and 82 carry no `duplicates`: 80 predates it, 82 couldn't read
    # its disc. Neither says nothing repeated.
    for name in ("job-80.json", "job-82.json"):
        assert "duplicates" not in load(name)
