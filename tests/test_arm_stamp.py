"""The raw folder's stamp, as the deployment writes it.

Each fixture is a real `arm-job.json`, copied from a raw folder, and together
they are every stamp on the share. The tests pin the rules *The raw folder's
stamp* in the design states, so a stamp that breaks the contract fails here
before any reader is built on it. A change to the stamp comes with a fixture
here.

ARM wrote these as each job ran:

- job 76: a DVD, its title map written after the fact
- job 77: a DVD, its title map written by the job
- job 78: a Blu-ray movie
- job 79: a Blu-ray movie with featurette variants
- job 80: a Blu-ray series disc from before `duplicates`
- job 82: a Blu-ray whose structure couldn't be read, so no `duplicates`
- job 83: a Blu-ray series disc whose play-all was skipped
- jobs 84, 85 and 86: later Blu-rays, each with a whole

The deployment backfilled these into folders older than the stamp, from ARM's
database and the job's own log:

- jobs 7 and 8: failed Rescuers rips, proven by their `_<stage>` suffix; their
  logs are gone, so no title map
- job 23: a failed Rescuers rip, proven by its suffix and its log
- job 25: the misidentified Polar Express, proven by its log alone
- job 27: *The Rescuers* of the fixtures table
"""

import json
from pathlib import Path

import pytest

STAMPS = Path(__file__).parent / "fixtures" / "stamps"
FIXTURES = sorted(STAMPS.glob("job-*.json"), key=lambda p: int(p.stem[4:]))
BACKFILLED = (7, 8, 23, 25, 27)
BASE = {
    "schema",
    "job_id",
    "label",
    "disctype",
    "crc_id",
    "stage",
    "start_time",
    "title_map",
}
# Each identifier in the order a title passes through it, disc to transcode.
TITLE_MAP = {
    "dvd": ["disc_title", "mkv", "handbrake_title"],
    "bluray": ["playlist", "handbrake_title"],
}


def load(job: int) -> dict:
    return json.loads((STAMPS / f"job-{job}.json").read_text())


def keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from keys(inner)


@pytest.fixture(params=FIXTURES, ids=lambda p: p.stem)
def stamp(request: pytest.FixtureRequest) -> dict:
    return json.loads(request.param.read_text())


def test_every_job_named_in_the_docstring_has_a_fixture():
    assert [p.stem for p in FIXTURES] == [
        f"job-{n}" for n in (*BACKFILLED, 76, 77, 78, 79, 80, 82, 83, 84, 85, 86)
    ]


def test_schema_one_holds_the_base_fields(stamp):
    assert stamp["schema"] == 1
    assert set(stamp) >= BASE
    assert isinstance(stamp["job_id"], int)


def test_no_stamp_keeps_a_retired_field(stamp):
    # `titles` and a bare `title` before 2026-10-26; `extracted`, a Blu-ray's
    # `playlists` and each title's `length` before 2026-10-28. Every stamp on
    # the share was rewritten each time.
    assert not {"title", "titles", "extracted", "playlists", "length"} & set(
        keys(stamp)
    )


def test_complete_agrees_with_its_problems(stamp):
    if "complete" not in stamp:
        # A backfilled stamp whose copy passed the size check: not recorded.
        assert stamp["job_id"] in BACKFILLED
        assert "problems" not in stamp
        return
    assert stamp["complete"] in (True, False, None)
    assert (stamp["complete"] is False) == bool(stamp["problems"])


def test_a_dvd_has_a_crc_and_a_blu_ray_none(stamp):
    if stamp["disctype"] == "dvd":
        assert isinstance(stamp["crc_id"], str)
    else:
        assert stamp["disctype"] == "bluray"
        assert stamp["crc_id"] is None


def test_a_title_map_traces_each_title_from_disc_to_transcode(stamp):
    if stamp["title_map"] is None:
        pytest.skip("no title map recorded")
    for title in stamp["title_map"]:
        assert list(title) == TITLE_MAP[stamp["disctype"]]
        if stamp["disctype"] == "dvd":
            assert isinstance(title["disc_title"], int)
            assert title["mkv"].endswith(".mkv")
        else:
            assert title["playlist"].endswith(".mpls")
    numbers = [t["handbrake_title"] for t in stamp["title_map"] if t["handbrake_title"]]
    assert len(numbers) == len(set(numbers))


def test_a_blu_rays_map_includes_the_titles_it_skipped(stamp):
    if stamp["disctype"] != "bluray" or not stamp.get("duplicates"):
        pytest.skip("not a Blu-ray with `duplicates`")
    mapped = {t["handbrake_title"]: t["playlist"] for t in stamp["title_map"]}
    for skipped in stamp["duplicates"]["skipped"]:
        assert mapped[skipped["handbrake_title"]] == skipped["playlist"]


def test_featurette_variants_map_to_their_own_playlists():
    # Job 79's log shows these, which length alone pairs the wrong way round.
    mapped = {t["handbrake_title"]: t["playlist"] for t in load(79)["title_map"]}
    assert (mapped[76], mapped[84]) == ("01227.mpls", "01235.mpls")


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
            explained.add(whole["handbrake_title"])
        elif whole["kept"] == "whole":
            explained.update(part["handbrake_title"] for part in whole["parts"])
    for skipped in duplicates["skipped"]:
        assert source in skipped
        assert skipped["reason"]
    assert {s["handbrake_title"] for s in duplicates["skipped"]} <= explained


def test_a_series_play_all_is_skipped_and_its_episodes_placed():
    duplicates = load(83)["duplicates"]
    assert [s["handbrake_title"] for s in duplicates["skipped"]] == [7]
    (whole,) = duplicates["wholes"]
    assert (whole["handbrake_title"], whole["kept"], whole["interleaved"]) == (
        7,
        "parts",
        False,
    )
    assert [p["handbrake_title"] for p in whole["parts"]] == [2, 3, 4]
    assert [p["start"] for p in whole["parts"]] == [0.0, 2859.79, 5658.62]


def test_a_missing_field_reads_as_not_recorded():
    # Jobs 80 and 82 carry no `duplicates`: 80 predates it, 82 couldn't read
    # its disc. Neither says nothing repeated. A backfilled stamp has none
    # either, since its job skipped nothing, and job 7's no `complete`, since a
    # backup's hash check can't be rerun.
    for job in (80, 82, *BACKFILLED):
        assert "duplicates" not in load(job)
    assert "complete" not in load(7)
