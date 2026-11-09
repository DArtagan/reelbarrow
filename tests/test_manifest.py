"""The manifest's contract, held against real jobs exported.

Each case is a folder in `fixtures/manifests/`, named for the case. Its
`arm-db.json` is the exporter's input, in ARM's vocabulary: the job row's
columns the exporter reads and the job's raw-copy record, the patch's document
as the deployment's migration writes it. Its `manifest.json` is the exporter's
output from them. The tests pin the rules *The manifest* and *The raw copy's
record* in the design state, and the model in `reelbarrow.manifest` enforces
the rest, so a manifest that breaks the contract fails here before any reader
is built on it. A change to either brings a fixture here.

Recorded as their jobs ran:

- `dvd-series`: a DVD series disc
- `dvd-series-map-added-later`: the same disc, its title map recorded after
  the job
- `dvd-whole-kept`: a movie's bonus DVD, its documentary kept whole and its
  three parts skipped
- `bluray-movie`: a Blu-ray movie whose feature ARM renamed for the film
- `bluray-featurette-variants`: a Blu-ray movie whose featurettes come in
  variants that share their clips
- `bluray-series-before-duplicates`: a Blu-ray series disc from before titles
  were compared
- `bluray-structure-unread`: a Blu-ray whose structure couldn't be read
- `bluray-parts-kept`: a Blu-ray series disc whose play-all was skipped
- `bluray-parts-kept-among-others`: the same, with titles beside the play-all
  and its episodes
- `bluray-whole-kept`: a Blu-ray whose whole was kept and every part skipped
- `bluray-whole-kept-among-others`: the same, with titles beside the whole and
  its parts
- `bluray-shuffled`: a Blu-ray series disc whose episodes are offered as
  hundreds of shuffled playlists, one shuffle a play-all's
- `bluray-backup-errored`: a Blu-ray whose backup failed before its checks ran

Recorded afterwards, from ARM's database and the job's own log:

- `backfilled-bluray-log-lost`: a failed rip, proven by its `_<stage>` suffix;
  its log is gone, so no title map
- `backfilled-bluray-log-lost-rerip`: the same disc ripped again, failed the
  same way
- `backfilled-bluray-failed-rip`: a failed rip, proven by its suffix and its
  log, its identity copied by ARM from an earlier job
- `backfilled-bluray-misidentified`: a misidentified disc, corrected by hand in
  ARM's UI
- `backfilled-bluray-two-films`: two films on one disc, *The Rescuers* of the
  fixtures table

With no raw copy recorded:

- `dvd-before-the-record`: a DVD ripped before the record, *The Hallelujah
  Trail*'s successful job
- `dvd-failed-rip`: one of its failed jobs
- `not-identified`: a disc ARM couldn't identify
"""

import json
import re
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

import arm_db
import pytest
from pydantic import ValidationError

from reelbarrow import manifest
from reelbarrow.exporter import ArmPath, Exporter
from reelbarrow.manifest import Manifest, ShareRef

CASES_DIR = Path(__file__).parent / "fixtures" / "manifests"
CASES = sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir())
ROOT = ArmPath.parse("/root/video=import/automatic-ripping-machine")
# Where ARM's container sees the share in the deployment these came from.
SHARE = "import/automatic-ripping-machine"


def load(case: str) -> dict:
    return json.loads((CASES_DIR / case / "manifest.json").read_text())


def by_key(built: dict) -> dict:
    """Its titles by the disc's own number."""
    key = "playlist" if built["disc"]["type"] == "bluray" else "disc_title"
    return {title[key]: title for title in built.get("titles", [])}


def name(ref: dict | None) -> str | None:
    return PurePosixPath(ref["path"]).name if ref else None


@pytest.fixture(params=CASES)
def case(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def built(case: str) -> dict:
    return load(case)


def test_every_case_in_the_docstring_has_a_fixture():
    assert sorted(re.findall(r"^- `([a-z-]+)`:", __doc__, re.MULTILINE)) == CASES
    for case in CASES:
        assert sorted(p.name for p in (CASES_DIR / case).iterdir()) == [
            "arm-db.json",
            "manifest.json",
        ]


def test_each_case_exports_as_frozen(case, tmp_path):
    fixture = json.loads((CASES_DIR / case / "arm-db.json").read_text())
    job = fixture["job"]
    db = arm_db.create(tmp_path / "arm.db")
    arm_db.insert(db, "job", arm_db.job(**job))
    if fixture["raw_copy"] is not None:
        document = json.dumps(fixture["raw_copy"])
        arm_db.insert(
            db, "reelbarrow_raw_copy", {"job_id": job["job_id"], "document": document}
        )
    out = tmp_path / "manifests"
    out.mkdir()
    exporter = Exporter(db=db, out=out, root=ROOT, zone=ZoneInfo("Etc/UTC"))
    assert exporter.run_pass()
    (written,) = out.glob("manifest-*.json")
    assert json.loads(written.read_text()) == load(case)
    assert written.name == f"manifest-arm-{job['job_id']}-{job['stage']}.json"


def test_each_case_reads_back_as_written(built):
    """What the exporter writes, intake parses to the same manifest."""
    assert Manifest.model_validate(built).to_json() == built


def test_the_schema_file_is_current():
    committed = json.loads(manifest.SCHEMA_FILE.read_text())
    assert committed == manifest.schema(), "run: python -m reelbarrow.manifest"


def test_the_envelope(built):
    assert built["schema"] == 1
    assert built["source"] == "arm"
    assert re.fullmatch(r"\d+-\d+", built["id"])
    if built["state"] == "succeeded":
        assert built["finish_time"] is not None


def test_every_path_is_a_share_reference_in_arms_slice(built):
    def refs(value):
        if isinstance(value, dict):
            if "path" in value:
                yield value
            else:
                for inner in value.values():
                    yield from refs(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from refs(inner)

    found = list(refs(built))
    assert found
    for ref in found:
        assert set(ref) == {"path"}
        assert ShareRef.model_validate(ref).path.startswith(f"{SHARE}/")


def test_a_disc_arm_never_identified_says_so():
    identity = load("not-identified")["identity"]
    assert {claim["reason"] for claim in identity.values()} == {"not_identified"}


def test_a_correction_in_arms_ui_is_a_persons():
    identity = load("backfilled-bluray-misidentified")["identity"]
    assert identity["title"] == {
        "value": "The-Polar-Express",
        "reason": "set_by_person",
    }


def test_an_identity_arm_copied_by_label_says_so():
    # Job 5's correction, copied by ARM's job_dupe_check onto the same disc
    # ripped again. Its IMDb ID isn't copied, so it has none.
    for case in ("backfilled-bluray-failed-rip", "backfilled-bluray-two-films"):
        identity = load(case)["identity"]
        assert identity["title"] == {
            "value": "The Rescuers",
            "reason": "copied_from_earlier_job",
        }
        assert identity["imdb_id"]["value"] is None


def test_a_dvd_has_a_crc64_and_a_blu_ray_none(built):
    disc = built["disc"]
    if disc["type"] == "dvd":
        assert disc["crc64"] is not None
    else:
        assert disc["type"] == "bluray"
        assert disc["crc64"] is None


def test_each_check_says_what_it_found(case, built):
    if "raw" not in built:
        pytest.skip("no raw copy recorded")
    check = built["raw"]["check"]
    if case.startswith("backfilled-"):
        # Recorded afterwards: the hashes can't be checked again.
        assert check["hashes"] == "not_run"
    if built["state"] == "succeeded" and not case.startswith("backfilled-"):
        assert check == {"sizes": "passed", "hashes": "passed"}
    assert load("bluray-backup-errored")["raw"]["check"] == {
        "sizes": "not_run",
        "hashes": "not_run",
    }


def test_no_raw_copy_is_not_recorded_rather_than_none():
    for case in ("dvd-before-the-record", "dvd-failed-rip", "not-identified"):
        assert {"raw", "titles"} & set(load(case)) == set()


def test_titles_trace_each_title_from_disc_to_transcode(built):
    if "titles" not in built:
        pytest.skip("no title map recorded")
    raw = built["raw"]["folder"]["path"]
    completed = built["completed"]["folder"]["path"]
    for title in built["titles"]:
        if built["disc"]["type"] == "dvd":
            if "extracted" in title:
                assert title["extracted"]["path"].startswith(f"{raw}/titles/")
        else:
            assert "extracted" not in title
        if title.get("transcode"):
            assert title["transcode"]["path"].startswith(f"{completed}/")


def test_featurette_variants_map_to_their_own_playlists():
    # The job's log shows these, which length alone pairs the wrong way round.
    titles = by_key(load("bluray-featurette-variants"))
    assert name(titles["01227.mpls"]["transcode"]) == "title_76.mkv"
    assert name(titles["01235.mpls"]["transcode"]) == "title_84.mkv"


def test_a_feature_arm_renamed_is_recorded_from_arms_main_feature():
    # Before the patch that keeps title_N.mkv, ARM named the feature for the
    # film; its main-feature track says which title that was.
    for case, film in (
        ("bluray-movie", "Downton-Abbey--A-New-Era (2022).mkv"),
        ("bluray-featurette-variants", "Downton-Abbey (2019).mkv"),
    ):
        titles = load(case)["titles"]
        assert all("transcode" in t for t in titles), case
        assert [name(t["transcode"]) for t in titles].count(film) == 1


def test_a_series_play_all_is_skipped_and_its_episodes_placed():
    titles = by_key(load("bluray-parts-kept-among-others"))
    (whole,) = [t for t in titles.values() if "parts" in t]
    assert whole["reason"] == "played_by_kept_titles"
    assert "played_by" not in whole
    assert whole["interleaved"] is False
    assert [p["start"] for p in whole["parts"]] == [0.0, 2859.79, 5658.62]
    for part in whole["parts"]:
        assert titles[part["playlist"]]["transcode"] is not None


def test_a_movie_discs_whole_is_kept_and_its_parts_placed_in_playback_seconds():
    titles = by_key(load("dvd-whole-kept"))
    (whole,) = [t for t in titles.values() if "parts" in t]
    assert whole["transcode"] is not None
    for part in whole["parts"]:
        # Its whole says what plays it, so nothing else does.
        assert titles[part["disc_title"]]["reason"] == "played_by_kept_titles"
        assert "played_by" not in titles[part["disc_title"]]
    # The whole's MKV has chapters at 1086.118 and 2854.385. lsdvd's unscaled
    # lengths would put these about a second early.
    assert [p["start"] for p in whole["parts"]] == [0.0, 1086.118, 2854.385]


def test_shuffles_name_the_title_they_repeat_through_a_chain():
    titles = by_key(load("bluray-shuffled"))
    shuffles = [t for t in titles.values() if "played_by" in t]
    assert len(shuffles) == 297
    # One repeats a play-all, which its episodes play in turn.
    (play_all,) = [t for t in titles.values() if "parts" in t]
    via = [t for t in shuffles if t["played_by"]["playlist"] == play_all["playlist"]]
    assert via
    assert play_all["reason"] == "played_by_kept_titles"


def test_a_missing_field_reads_as_not_recorded():
    # Titles not compared, before it was done or on a disc whose structure
    # couldn't be read, or recorded afterwards: nothing is known of repeats.
    uncompared = [
        "bluray-series-before-duplicates",
        "bluray-structure-unread",
        *(case for case in CASES if case.startswith("backfilled-")),
    ]
    for case in uncompared:
        built = load(case)
        assert "titles_compared" not in built["raw"]
        assert all("parts" not in t for t in built.get("titles", []))
    assert "titles" not in load("backfilled-bluray-log-lost")


# --- the model refuses a manifest that breaks the contract ------------------


def broken(change) -> dict:
    built = load("dvd-whole-kept")
    change(built)
    return built


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(schema=2),
        lambda m: m.update(raw=None),
        lambda m: m["raw"].update(check={"sizes": "fine", "hashes": "passed"}),
        lambda m: m["raw"].update(problems=["x"]),
        lambda m: m["raw"].pop("titles_compared"),
        lambda m: m["titles"][1].update(reason=None),
        lambda m: m["titles"][1].update(played_by={"disc_title": 1}),
        lambda m: m["titles"][0].update(parts=m["titles"][0]["parts"][:1]),
        lambda m: m["titles"][0].pop("interleaved"),
        lambda m: m["titles"].append(dict(m["titles"][1])),
        lambda m: m["completed"]["folder"].update(path="/abs/olute"),
    ],
)
def test_the_model_refuses(change):
    with pytest.raises(ValidationError):
        Manifest.model_validate(broken(change))


def test_the_model_reads_past_fields_it_doesnt_know():
    built = load("dvd-whole-kept") | {"added_later": 1}
    assert "added_later" not in Manifest.model_validate(built).to_json()


# --- the share reference ----------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/import/x",
        "import//x",
        "import/./x",
        "import/../x",
        "..",
        "import/x/",
        "a\0b",
    ],
)
def test_a_share_path_is_relative_plain_and_whole(path):
    with pytest.raises(ValidationError):
        ShareRef(path=path)


def test_a_share_path_keeps_its_name_exactly():
    path = f"{SHARE}/raw/Robin Hood/titles/Robin Hood (Unrated) [2010]-E1_t00.mkv"
    assert ShareRef(path=path).model_dump() == {"path": path}


def test_a_share_reference_resolves_under_this_processs_root(tmp_path):
    root = tmp_path / "video"
    (root / "import").mkdir(parents=True)
    resolved = ShareRef(path="import/x.mkv").resolve(root)
    assert resolved == (root / "import/x.mkv").resolve()
    (root / "import" / "out").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        ShareRef(path="import/out/secret").resolve(root)
