"""The manifest's contract, held against real jobs exported.

Each case is a real ARM job: `fixtures/arm/<case>.json` holds its row's columns
the exporter reads and its raw copy's record, as the deployment's migration
writes it from the job's `arm-job.json`, and `fixtures/manifests/<case>.json`
is the manifest the exporter makes of them. The tests pin the rules *The
manifest* and *The raw copy's record* in the design state, so a manifest that
breaks the contract fails here before any reader is built on it. A change to
either brings a fixture here.

Recorded as their jobs ran:

- `dvd-series`: a DVD series disc
- `dvd-series-map-added-later`: the same disc, its title map recorded after
  the job
- `dvd-whole-kept`: a movie's bonus DVD, its documentary kept whole and its
  three parts skipped
- `bluray-movie`: a Blu-ray movie whose feature ARM renamed for the film
- `bluray-featurette-variants`: a Blu-ray movie whose featurettes come in
  variants that share their clips
- `bluray-series-before-duplicates`: a Blu-ray series disc from before
  skipped titles were recorded
- `bluray-structure-unread`: a Blu-ray whose structure couldn't be read
- `bluray-parts-kept`: a Blu-ray series disc whose play-all was skipped
- `bluray-parts-kept-among-others`: the same, with titles beside the play-all
  and its episodes
- `bluray-whole-kept`: a Blu-ray whose whole was kept and every part skipped
- `bluray-whole-kept-among-others`: the same, with titles beside the whole and
  its parts
- `bluray-running`: a Blu-ray mid-backup, its copy not yet checked

Recorded afterwards, from ARM's database and the job's own log:

- `backfilled-bluray-log-lost`: a failed rip, proven by its `_<stage>` suffix;
  its log is gone, so no title map
- `backfilled-bluray-log-lost-rerip`: the same disc ripped again, failed the
  same way
- `backfilled-bluray-failed-rip`: a failed rip, proven by its suffix and its log
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

from reelbarrow.exporter import ArmRoot, Exporter
from reelbarrow.manifest import (
    CompleteReason,
    IdentityReason,
    RawForm,
    ShareRef,
    ShareRefError,
    State,
    TitleReason,
)

FIXTURES = Path(__file__).parent / "fixtures"
INPUTS = FIXTURES / "arm"
MANIFESTS = FIXTURES / "manifests"
CASES = sorted(p.stem for p in INPUTS.glob("*.json"))
ROOT = ArmRoot.parse("/root/video=import/automatic-ripping-machine")
# Where ARM's container sees the share in the deployment these came from.
SHARE = "import/automatic-ripping-machine"


def load(case: str) -> dict:
    return json.loads((MANIFESTS / f"{case}.json").read_text())


def by_key(manifest: dict) -> dict:
    """Its titles by the disc's own number."""
    key = "playlist" if manifest["disc"]["type"] == "bluray" else "disc_title"
    return {title[key]: title for title in manifest.get("titles", [])}


def name(ref: dict | None) -> str | None:
    return PurePosixPath(ref["path"]).name if ref else None


@pytest.fixture(params=CASES)
def case(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def manifest(case: str) -> dict:
    return load(case)


def test_every_case_in_the_docstring_has_a_fixture():
    assert sorted(re.findall(r"^- `([a-z-]+)`:", __doc__, re.MULTILINE)) == CASES
    assert sorted(p.stem for p in MANIFESTS.glob("*.json")) == CASES


def test_each_case_exports_as_frozen(case, tmp_path):
    fixture = json.loads((INPUTS / f"{case}.json").read_text())
    db = arm_db.create(tmp_path / "arm.db")
    arm_db.insert(db, "job", arm_db.job(**fixture["job"]))
    if fixture["raw_copy"] is not None:
        document = json.dumps(fixture["raw_copy"])
        arm_db.insert(
            db,
            "reelbarrow_raw_copy",
            {"job_id": fixture["job"]["job_id"], "document": document},
        )
    out = tmp_path / "manifests"
    out.mkdir()
    exporter = Exporter(db=db, out=out, root=ROOT, zone=ZoneInfo("Etc/UTC"))
    assert exporter.run_pass()
    (written,) = out.glob("manifest-*.json")
    assert json.loads(written.read_text()) == load(case)
    job = fixture["job"]
    assert written.name == f"manifest-arm-{job['job_id']}-{job['stage']}.json"


def test_the_envelope(manifest):
    assert manifest["schema"] == 1
    assert manifest["source"] == "arm"
    assert re.fullmatch(r"\d+-\d+", manifest["id"])
    assert State(manifest["state"])
    for field in ("start_time", "finish_time"):
        if manifest[field] is not None:
            assert manifest[field].endswith("+00:00")
    if manifest["state"] == "succeeded":
        assert manifest["finish_time"] is not None


def test_every_path_is_a_share_reference_in_arms_slice(manifest):
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

    found = list(refs(manifest))
    assert found
    for ref in found:
        assert set(ref) == {"path"}
        assert ShareRef.from_json(ref).path.startswith(f"{SHARE}/")


def test_identity_says_who_supplied_each_field(manifest):
    assert set(manifest["identity"]) == {"title", "year", "imdb_id", "kind"}
    for claim in manifest["identity"].values():
        assert set(claim) == {"value", "reason"}
        assert IdentityReason(claim["reason"])


def test_a_disc_arm_never_identified_says_so():
    identity = load("not-identified")["identity"]
    assert {claim["reason"] for claim in identity.values()} == {"not_identified"}


def test_a_correction_in_arms_ui_is_a_persons():
    identity = load("backfilled-bluray-misidentified")["identity"]
    assert identity["title"] == {
        "value": "The-Polar-Express",
        "reason": "set_by_person",
    }


def test_a_dvd_has_a_crc64_and_a_blu_ray_none(manifest):
    disc = manifest["disc"]
    if disc["type"] == "dvd":
        assert re.fullmatch(r"[0-9a-f]{16}", disc["crc64"])
    else:
        assert disc["type"] == "bluray"
        assert disc["crc64"] is None


def test_completeness_agrees_with_its_problems(case, manifest):
    if "raw" not in manifest:
        pytest.skip("no raw copy recorded")
    raw = manifest["raw"]
    assert RawForm(raw["form"])
    complete = raw["complete"]
    reason = CompleteReason(complete["reason"])
    assert (complete["value"] is False) == bool(raw["problems"])
    if reason is CompleteReason.NOT_CHECKED:
        assert complete["value"] is None
    if reason is CompleteReason.SIZES:
        # A copy recorded afterwards is never shown complete.
        assert case.startswith("backfilled-")
        assert complete["value"] is not True
    assert ("image" in raw) == (raw["form"] == "dvd-image")


def test_no_raw_copy_is_not_recorded_rather_than_none():
    for case in ("dvd-before-the-record", "dvd-failed-rip", "not-identified"):
        assert {"raw", "titles", "wholes"} & set(load(case)) == set()


def test_titles_trace_each_title_from_disc_to_transcode(manifest):
    if "titles" not in manifest:
        pytest.skip("no title map recorded")
    titles = manifest["titles"]
    keys = list(by_key(manifest))
    assert len(keys) == len(titles)
    raw = manifest["raw"]["folder"]["path"]
    completed = manifest["completed"]["folder"]["path"]
    for title in titles:
        if manifest["disc"]["type"] == "dvd":
            assert isinstance(title["disc_title"], int)
            if "extracted" in title:
                assert title["extracted"]["path"].startswith(f"{raw}/titles/")
                assert title["extracted"]["path"].endswith(".mkv")
            else:
                assert title["reason"] == "not_extracted"
        else:
            assert title["playlist"].endswith(".mpls")
            assert "extracted" not in title
        if "transcode" in title:
            if title["transcode"] is None:
                assert TitleReason(title["reason"])
            else:
                assert title["reason"] is None
                assert title["transcode"]["path"].startswith(f"{completed}/")
        else:
            assert "reason" not in title
    transcodes = [t["transcode"]["path"] for t in titles if t.get("transcode")]
    assert len(transcodes) == len(set(transcodes))


def test_featurette_variants_map_to_their_own_playlists():
    # The job's log shows these, which length alone pairs the wrong way round.
    titles = by_key(load("bluray-featurette-variants"))
    assert name(titles["01227.mpls"]["transcode"]) == "title_76.mkv"
    assert name(titles["01235.mpls"]["transcode"]) == "title_84.mkv"


def test_a_feature_arm_renamed_is_not_recorded():
    titles = load("bluray-movie")["titles"]
    assert [name(t.get("transcode")) for t in titles].count(None) == 1
    assert all("reason" not in t for t in titles if "transcode" not in t)


def test_wholes_skip_only_what_they_account_for(manifest):
    if "wholes" not in manifest:
        pytest.skip("not scanned for titles that repeat")
    titles = by_key(manifest)
    key = "playlist" if manifest["disc"]["type"] == "bluray" else "disc_title"
    accounted = {}
    for whole in manifest["wholes"]:
        assert whole["kept"] in ("parts", "whole", "both")
        assert isinstance(whole["interleaved"], bool)
        assert len(whole["parts"]) >= 2
        starts = [part["start"] for part in whole["parts"]]
        assert starts == sorted(starts)
        assert whole[key] in titles
        assert all(part[key] in titles for part in whole["parts"])
        if whole["kept"] == "parts":
            accounted[whole[key]] = "parts_kept"
        elif whole["kept"] == "whole":
            accounted |= {part[key]: "whole_kept" for part in whole["parts"]}
    for number, title in titles.items():
        if title.get("reason") in ("parts_kept", "whole_kept"):
            assert accounted[number] == title["reason"]


def test_a_series_play_all_is_skipped_and_its_episodes_placed():
    manifest = load("bluray-parts-kept-among-others")
    skipped = [
        k for k, t in by_key(manifest).items() if t.get("reason") == "parts_kept"
    ]
    (whole,) = manifest["wholes"]
    assert skipped == [whole["playlist"]]
    assert (whole["kept"], whole["interleaved"]) == ("parts", False)
    assert [p["start"] for p in whole["parts"]] == [0.0, 2859.79, 5658.62]
    for part in whole["parts"]:
        assert by_key(manifest)[part["playlist"]]["transcode"] is not None


def test_a_movie_discs_whole_is_kept_and_its_parts_placed_in_playback_seconds():
    manifest = load("dvd-whole-kept")
    (whole,) = manifest["wholes"]
    assert (whole["kept"], whole["interleaved"]) == ("whole", False)
    titles = by_key(manifest)
    assert titles[whole["disc_title"]]["transcode"] is not None
    assert [titles[p["disc_title"]]["reason"] for p in whole["parts"]] == [
        "whole_kept"
    ] * 3
    # The whole's MKV has chapters at 1086.118 and 2854.385. lsdvd's unscaled
    # lengths would put these about a second early.
    assert [p["start"] for p in whole["parts"]] == [0.0, 1086.118, 2854.385]


def test_a_missing_field_reads_as_not_recorded():
    # Before skipped titles were recorded, or from a job that couldn't read its
    # disc, a record has no `wholes`, and neither says nothing repeated. One
    # recorded afterwards has none either, since its job skipped nothing.
    unscanned = [
        "bluray-series-before-duplicates",
        "bluray-structure-unread",
        *(case for case in CASES if case.startswith("backfilled-")),
    ]
    for case in unscanned:
        assert "wholes" not in load(case)
    assert "titles" not in load("backfilled-bluray-log-lost")
    assert load("bluray-running")["raw"]["complete"] == {
        "value": None,
        "reason": "not_checked",
    }
    assert load("bluray-running")["state"] == "running"


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
    with pytest.raises(ShareRefError):
        ShareRef(path)


def test_a_share_path_keeps_its_name_exactly():
    path = "import/automatic-ripping-machine/raw/Robin Hood/titles/Robin Hood (Unrated) [2010]-E1_t00.mkv"
    assert ShareRef(path).to_json() == {"path": path}
    assert ShareRef.from_json({"path": path}) == ShareRef(path)
    with pytest.raises(ShareRefError):
        ShareRef.from_json(path)


def test_a_share_reference_resolves_under_this_processs_root(tmp_path):
    root = tmp_path / "video"
    (root / "import").mkdir(parents=True)
    assert ShareRef("import/x.mkv").resolve(root) == (root / "import/x.mkv").resolve()
    (root / "import" / "out").symlink_to(tmp_path)
    with pytest.raises(ShareRefError, match="outside"):
        ShareRef("import/out/secret").resolve(root)
