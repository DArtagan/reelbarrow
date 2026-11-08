"""The raw folder's stamp, as the deployment writes it.

Each fixture is a real `arm-job.json`, copied from a raw folder and named for
the case it holds. The tests pin the rules *The raw folder's stamp* in the
design states, so a stamp that breaks the contract fails here before any reader
is built on it. A change to the stamp comes with a fixture here.

ARM wrote these as each job ran:

- `dvd-series`: a DVD series disc, its title map written by the job
- `dvd-series-map-added-later`: the same disc, its title map written after the
  job
- `dvd-whole-kept`: a movie's bonus DVD, its documentary kept whole and its
  three parts skipped
- `bluray-movie`: a Blu-ray movie
- `bluray-featurette-variants`: a Blu-ray movie whose featurettes come in
  variants that share their clips
- `bluray-series-before-duplicates`: a Blu-ray series disc from before
  `duplicates`
- `bluray-structure-unread`: a Blu-ray whose structure couldn't be read, so no
  `duplicates`
- `bluray-parts-kept`: a Blu-ray series disc whose play-all was skipped
- `bluray-parts-kept-among-others`: the same, with titles beside the play-all
  and its episodes
- `bluray-whole-kept`: a Blu-ray whose whole was kept and every part skipped
- `bluray-whole-kept-among-others`: the same, with titles beside the whole and
  its parts

The deployment backfilled these into folders older than the stamp, from ARM's
database and the job's own log:

- `backfilled-bluray-log-lost`: a failed rip, proven by its `_<stage>` suffix;
  its log is gone, so no title map
- `backfilled-bluray-log-lost-rerip`: the same disc ripped again, failed the
  same way
- `backfilled-bluray-failed-rip`: a failed rip, proven by its suffix and its log
- `backfilled-bluray-misidentified`: a misidentified disc, proven by its log
  alone
- `backfilled-bluray-two-films`: two films on one disc, *The Rescuers* of the
  fixtures table
"""

import json
import re
from pathlib import Path

import pytest

STAMPS = Path(__file__).parent / "fixtures" / "stamps"
NAMES = sorted(p.stem for p in STAMPS.glob("*.json"))
BACKFILLED = [name for name in NAMES if name.startswith("backfilled-")]
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


def load(name: str) -> dict:
    return json.loads((STAMPS / f"{name}.json").read_text())


def keys(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from keys(inner)


@pytest.fixture(params=NAMES)
def name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def stamp(name: str) -> dict:
    return load(name)


def test_every_case_in_the_docstring_has_a_fixture():
    assert sorted(re.findall(r"^- `([a-z-]+)`:", __doc__, re.MULTILINE)) == NAMES


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


def test_complete_agrees_with_its_problems(name, stamp):
    if "complete" not in stamp:
        # A backfilled stamp whose copy passed the size check: not recorded.
        assert name in BACKFILLED
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
    # The job's log shows these, which length alone pairs the wrong way round.
    mapped = {
        t["handbrake_title"]: t["playlist"]
        for t in load("bluray-featurette-variants")["title_map"]
    }
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
    duplicates = load("bluray-parts-kept-among-others")["duplicates"]
    assert [s["handbrake_title"] for s in duplicates["skipped"]] == [7]
    (whole,) = duplicates["wholes"]
    assert (whole["handbrake_title"], whole["kept"], whole["interleaved"]) == (
        7,
        "parts",
        False,
    )
    assert [p["handbrake_title"] for p in whole["parts"]] == [2, 3, 4]
    assert [p["start"] for p in whole["parts"]] == [0.0, 2859.79, 5658.62]


def test_a_movie_discs_whole_is_kept_and_its_parts_placed_in_playback_seconds():
    duplicates = load("dvd-whole-kept")["duplicates"]
    assert [s["handbrake_title"] for s in duplicates["skipped"]] == [4, 5, 6]
    (whole,) = duplicates["wholes"]
    assert (whole["handbrake_title"], whole["kept"], whole["interleaved"]) == (
        3,
        "whole",
        False,
    )
    assert [p["handbrake_title"] for p in whole["parts"]] == [4, 5, 6]
    # The whole's MKV has chapters at 1086.118 and 2854.385. lsdvd's unscaled
    # lengths would put these about a second early.
    assert [p["start"] for p in whole["parts"]] == [0.0, 1086.118, 2854.385]


def test_a_missing_field_reads_as_not_recorded():
    # A stamp from before `duplicates`, or from a job that couldn't read its
    # disc, carries none, and neither says nothing repeated. A backfilled stamp
    # has none either, since its job skipped nothing, and no `complete` unless
    # its copy failed, since a backup's hash check can't be rerun.
    unrecorded = ("bluray-series-before-duplicates", "bluray-structure-unread")
    for name in (*unrecorded, *BACKFILLED):
        assert "duplicates" not in load(name)
    assert "complete" not in load("backfilled-bluray-log-lost")
