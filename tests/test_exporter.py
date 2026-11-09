"""The exporter that copies ARM's jobs out of its database as manifests.

Against a database built like the deployed one (`arm_db`), with synthetic rows.
Real jobs, exported, are the contract's fixtures in `test_manifest`.
"""

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import arm_db
import pytest

from reelbarrow import cli, exporter
from reelbarrow.exporter import ArmRoot, Exporter, SerialiseError, build, connect

ROOT = ArmRoot.parse("/root/video=import/automatic-ripping-machine")
UTC = ZoneInfo("Etc/UTC")
NAME = "manifest-arm-{}-176107498997.json"


@pytest.fixture
def db(tmp_path):
    return arm_db.create(tmp_path / "arm.db")


@pytest.fixture
def out(tmp_path):
    path = tmp_path / "manifests"
    path.mkdir()
    return path


@pytest.fixture
def export(db, out):
    return Exporter(db=db, out=out, root=ROOT, zone=UTC, timeout=0.05)


def manifests(out):
    return sorted(p.name for p in out.glob("manifest-*.json"))


def load(out, job_id):
    return json.loads((out / NAME.format(job_id)).read_text())


def stat(out, job_id):
    st = (out / NAME.format(job_id)).stat()
    return st.st_ino, st.st_mtime_ns


def one(job, document=None, zone=UTC):
    """The manifest of one job row, through the database's own types."""
    return build(arm_db.job(**job) if "job_id" in job else job, document, ROOT, zone)


# --- what a manifest says ---------------------------------------------------


def test_a_job_and_its_raw_copy(db, export, out):
    arm_db.insert(db, "job", arm_db.job(7))
    arm_db.insert(db, "reelbarrow_raw_copy", arm_db.raw_copy(7))
    assert export.run_pass()
    assert load(out, 7) == {
        "schema": 1,
        "source": "arm",
        "id": "7-176107498997",
        "state": "succeeded",
        "start_time": "2026-10-21T19:49:49.973701+00:00",
        "finish_time": "2026-10-21T21:02:13.204518+00:00",
        "errors": None,
        "disc": {"type": "dvd", "label": "SAMPLE_MOVIE", "crc64": "1a2b3c4d5e6f7081"},
        "identity": {
            "title": {"value": "Sample-Movie", "reason": "lookup"},
            "year": {"value": "1965", "reason": "lookup"},
            "imdb_id": {"value": "tt0000000", "reason": "lookup"},
            "kind": {"value": "movie", "reason": "lookup"},
        },
        "completed": {
            "folder": {
                "path": "import/automatic-ripping-machine/completed/movies/Sample-Movie (1965)"
            }
        },
        "raw": {
            "form": "dvd-image",
            "folder": {"path": "import/automatic-ripping-machine/raw/SAMPLE_MOVIE"},
            "image": {
                "path": "import/automatic-ripping-machine/raw/SAMPLE_MOVIE/SAMPLE_MOVIE.iso"
            },
            "complete": {"value": True, "reason": "sizes_and_hashes"},
            "problems": [],
        },
        "titles": [
            {
                "disc_title": 1,
                "extracted": {
                    "path": "import/automatic-ripping-machine/raw/SAMPLE_MOVIE/titles/SAMPLE-B1_t00.mkv"
                },
                "transcode": {
                    "path": "import/automatic-ripping-machine/completed/movies/Sample-Movie (1965)/title_1.mkv"
                },
                "reason": None,
            },
            {"disc_title": 3, "transcode": None, "reason": "not_extracted"},
        ],
    }


def test_only_success_and_fail_are_final():
    states = {
        status: one({"job_id": 1, "status": status})["state"]
        for status in ("success", "fail", "active", "ripping", "transcoding", "waiting")
    }
    assert states == {
        "success": "succeeded",
        "fail": "failed",
        "active": "running",
        "ripping": "running",
        "transcoding": "running",
        "waiting": "running",
    }


def test_times_are_utc_from_arms_zone():
    denver = ZoneInfo("America/Denver")
    built = one({"job_id": 1, "start_time": "2026-10-21 13:49:49.973701"}, zone=denver)
    assert built["start_time"] == "2026-10-21T19:49:49.973701+00:00"
    # Across the change to standard time, a week later.
    built = one({"job_id": 1, "start_time": "2026-11-02 13:00:00"}, zone=denver)
    assert built["start_time"] == "2026-11-02T20:00:00+00:00"
    assert one({"job_id": 1, "stop_time": None})["finish_time"] is None


def test_the_id_survives_a_recreated_database():
    first = one({"job_id": 1, "stage": "177674072574"})
    again = one({"job_id": 1, "stage": "179417475679"})
    assert first["id"] != again["id"]
    with pytest.raises(SerialiseError, match="stage"):
        one({"job_id": 1, "stage": None})


def test_who_identified_a_job():
    identity = one(
        {
            "job_id": 25,
            "title": "The-Polar-Express",
            "title_auto": "The-Adventures-of-Mary-Kate-and-Ashley",
            "title_manual": "The-Polar-Express",
            "year": "2004",
            "year_auto": "1994",
            "year_manual": "2004",
            "imdb_id": "tt0338348",
            "imdb_id_auto": "tt0338348",
            "imdb_id_manual": None,
        }
    )["identity"]
    assert identity["title"] == {
        "value": "The-Polar-Express",
        "reason": "set_by_person",
    }
    assert identity["year"]["reason"] == "set_by_person"
    # A person left the ID ARM found.
    assert identity["imdb_id"]["reason"] == "lookup"


def test_a_year_set_by_arms_series_route_is_a_persons():
    # That route writes `year` and no `year_manual`.
    identity = one(
        {
            "job_id": 1,
            "title_manual": "Downton-Abbey",
            "year": "2010",
            "year_auto": "2019",
            "year_manual": None,
        }
    )["identity"]
    assert identity["year"]["reason"] == "set_by_person"


def test_a_job_arm_never_identified():
    identity = one(
        {
            "job_id": 4,
            "hasnicetitle": 0,
            "title": "not identified",
            "year": "None",
            "imdb_id": None,
            "video_type": "unknown",
            **{f"{c}_auto": None for c in ("title", "year", "imdb_id", "video_type")},
        }
    )["identity"]
    assert identity == {
        "title": {"value": "not identified", "reason": "not_identified"},
        "year": {"value": None, "reason": "not_identified"},
        "imdb_id": {"value": None, "reason": "not_identified"},
        "kind": {"value": None, "reason": "not_identified"},
    }


def test_no_raw_copy_recorded_leaves_raw_out():
    built = one({"job_id": 18})
    assert {"raw", "titles", "wholes"} & set(built) == set()


def test_a_job_that_never_got_a_folder_has_none():
    assert one({"job_id": 1, "path": None})["completed"] is None


def test_titles_are_absent_until_mapped_and_a_transcode_until_moved():
    record = json.loads(arm_db.raw_copy(1)["document"])
    built = one({"job_id": 1}, json.dumps(record | {"title_map": None}))
    assert "titles" not in built
    built = one({"job_id": 1}, json.dumps(record | {"transcodes": {}}))
    assert "transcode" not in built["titles"][0]
    assert "reason" not in built["titles"][0]


def test_titles_arm_skipped_say_why():
    playlists = {n: f"0000{n}.mpls" for n in range(1, 8)}

    def title(n):
        return {"handbrake_title": n, "playlist": playlists[n]}

    record = {
        "schema": 1,
        "folder": "/root/video/raw/Downton",
        "form": "bluray-backup",
        "complete": {"value": True, "reason": "sizes_and_hashes"},
        "problems": [],
        "title_map": [title(n) for n in range(1, 8)],
        "duplicates": {
            "skipped": [title(n) for n in (3, 4, 5, 6)],
            "wholes": [
                {**title(6), "kept": "parts", "interleaved": False,
                 "parts": [{**title(1), "start": 0.0}, {**title(2), "start": 60.5}]},
                {**title(7), "kept": "whole", "interleaved": False,
                 "parts": [{**title(3), "start": 0.0}, {**title(4), "start": 9.0}]},
            ],
        },
    }  # fmt: skip
    built = one({"job_id": 1, "disctype": "bluray"}, json.dumps(record))
    reasons = {t["playlist"]: t.get("reason") for t in built["titles"]}
    assert reasons == {
        "00001.mpls": None,
        "00002.mpls": None,
        "00003.mpls": "whole_kept",
        "00004.mpls": "whole_kept",
        "00005.mpls": "same_as_another",
        "00006.mpls": "parts_kept",
        "00007.mpls": None,
    }
    assert built["wholes"][0] == {
        "playlist": "00006.mpls",
        "kept": "parts",
        "interleaved": False,
        "parts": [
            {"playlist": "00001.mpls", "start": 0.0},
            {"playlist": "00002.mpls", "start": 60.5},
        ],
    }
    # HandBrake's numbering stays in the exporter.
    assert "handbrake_title" not in json.dumps(built)


@pytest.mark.parametrize(
    "path",
    [
        "/root/elsewhere/raw/X",
        "/root/video/../db/raw",
        "/root/videos/raw/X",
        "root/video/raw/X",
    ],
)
def test_a_path_outside_arms_slice_fails_the_job(path):
    record = json.loads(arm_db.raw_copy(1)["document"])
    with pytest.raises(SerialiseError):
        one({"job_id": 1}, json.dumps(record | {"folder": path}))


@pytest.mark.parametrize(
    "change",
    [
        {"schema": 2},
        {"form": "floppy"},
        {"complete": {"value": True, "reason": "looked fine"}},
        {"title_map": [{"handbrake_title": 1}]},
    ],
)
def test_a_raw_copy_it_cannot_read_fails_the_job(change):
    record = json.loads(arm_db.raw_copy(1)["document"])
    with pytest.raises(SerialiseError):
        one({"job_id": 1}, json.dumps(record | change))


def test_arm_root_is_parsed_strictly():
    assert ArmRoot.parse("/root/video/=import/arm").container == "/root/video"
    for value in (
        "/root/video",
        "root/video=import",
        "/root/video=/import",
        "/v=a/../b",
    ):
        with pytest.raises(ValueError):
            ArmRoot.parse(value)


# --- what a pass does -------------------------------------------------------


def test_never_the_config_table(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.insert(
        db,
        "config",
        {
            "CONFIG_ID": 1,
            "job_id": 1,
            "OMDB_API_KEY": arm_db.SECRET,
            "PO_USER_KEY": "u",
        },
    )
    export.run_pass()
    for path in out.iterdir():
        assert arm_db.SECRET not in path.read_text()


def test_a_database_without_the_patch_exports_no_raw(tmp_path, out):
    db = arm_db.create(tmp_path / "plain.db", raw_copy=False)
    arm_db.insert(db, "job", arm_db.job(1))
    assert Exporter(db=db, out=out, root=ROOT, zone=UTC).run_pass()
    assert "raw" not in load(out, 1)


def test_a_missing_column_stops_every_pass(db, export, out, caplog):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.execute(db, "ALTER TABLE job DROP COLUMN crc_id")
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert not export.run_pass()
    assert "no crc_id" in caplog.text
    # Nothing, liveness included, so the stale liveness raises the alert.
    assert list(out.iterdir()) == []


def test_a_column_arm_adds_changes_nothing(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1))
    export.run_pass()
    before = stat(out, 1)
    arm_db.execute(db, "ALTER TABLE job ADD COLUMN some_new_column VARCHAR(8)")
    export.run_pass()
    assert stat(out, 1) == before


def test_a_pass_over_several_jobs(db, export, out):
    for job_id in (1, 2, 3):
        arm_db.insert(db, "job", arm_db.job(job_id))
    arm_db.insert(db, "reelbarrow_raw_copy", arm_db.raw_copy(3))
    assert export.run_pass()
    assert manifests(out) == [NAME.format(n) for n in (1, 2, 3)]
    assert "raw" not in load(out, 1)
    assert load(out, 3)["raw"]["form"] == "dvd-image"


def test_a_status_change_rewrites_only_that_job(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1, status="success"))
    arm_db.insert(db, "job", arm_db.job(2, status="ripping", stop_time=None))
    export.run_pass()
    before = stat(out, 1)

    arm_db.execute(db, "UPDATE job SET status = 'transcoding' WHERE job_id = 2")
    export.run_pass()
    assert load(out, 2)["state"] == "running"

    arm_db.execute(
        db,
        "UPDATE job SET status = 'success', stop_time = ? WHERE job_id = 2",
        "2026-10-21 21:02:13.204518",
    )
    export.run_pass()
    assert load(out, 2)["state"] == "succeeded"
    assert load(out, 2)["finish_time"] == "2026-10-21T21:02:13.204518+00:00"
    assert stat(out, 1) == before


def test_a_raw_copy_change_rewrites_its_job(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.insert(db, "reelbarrow_raw_copy", arm_db.raw_copy(1, transcodes={}))
    export.run_pass()
    assert "transcode" not in load(out, 1)["titles"][0]
    document = arm_db.raw_copy(1)["document"]
    arm_db.execute(db, "UPDATE reelbarrow_raw_copy SET document = ?", document)
    export.run_pass()
    assert load(out, 1)["titles"][0]["transcode"]["path"].endswith("/title_1.mkv")


def test_an_unchanged_job_is_left_alone(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1))
    export.run_pass()
    before = stat(out, 1)
    export.run_pass()
    export.run_pass()
    assert stat(out, 1) == before


def test_a_deleted_row_leaves_its_manifest(db, export, out, caplog):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.insert(db, "job", arm_db.job(2))
    export.run_pass()
    kept = (out / NAME.format(1)).read_bytes()

    arm_db.execute(db, "DELETE FROM job WHERE job_id = 1")
    with caplog.at_level(logging.WARNING, logger="reelbarrow.exporter"):
        export.run_pass()
        export.run_pass()
    assert (out / NAME.format(1)).read_bytes() == kept
    assert manifests(out) == [NAME.format(1), NAME.format(2)]
    gone = [r for r in caplog.records if "row gone" in r.getMessage()]
    assert len(gone) == 1
    assert "job 1-176107498997" in gone[0].getMessage()


def test_a_recreated_database_overwrites_nothing(db, export, out, tmp_path):
    arm_db.insert(db, "job", arm_db.job(1))
    export.run_pass()
    kept = (out / NAME.format(1)).read_bytes()
    fresh = arm_db.create(tmp_path / "fresh.db")
    arm_db.insert(fresh, "job", arm_db.job(1, stage="179417475679", label="OTHER"))
    Exporter(db=fresh, out=out, root=ROOT, zone=UTC).run_pass()
    assert (out / NAME.format(1)).read_bytes() == kept
    assert len(manifests(out)) == 2


def test_replacement_is_atomic(db, export, out, monkeypatch):
    """A reader sees the old file or the new one, never part of either: the new
    content is written whole beside the old, then renamed over it."""
    arm_db.insert(db, "job", arm_db.job(1, status="ripping"))
    export.run_pass()
    name = NAME.format(1)
    old = (out / name).read_bytes()
    reader = open(out / name, "rb")  # noqa: SIM115

    real_replace = os.replace
    seen = []

    def replace(src, dst):
        if str(dst).endswith(name):
            # At the moment of the swap, the target is still whole, and the
            # temporary file is whole and invisible to a scan for manifests.
            assert (out / name).read_bytes() == old
            json.loads(Path(src).read_bytes())
            assert os.path.basename(src).startswith(".")
            assert manifests(out) == [name]
            seen.append(src)
        real_replace(src, dst)

    monkeypatch.setattr(exporter.os, "replace", replace)
    arm_db.execute(db, "UPDATE job SET status = 'success'")
    export.run_pass()

    assert len(seen) == 1
    assert load(out, 1)["state"] == "succeeded"
    # Replaced, not rewritten in place: a reader holding the old file still
    # reads all of it.
    assert reader.read() == old
    reader.close()
    assert [p.name for p in out.iterdir() if p.name.startswith(".")] == []


def test_a_failed_write_is_retried_next_pass(db, export, out, monkeypatch):
    arm_db.insert(db, "job", arm_db.job(1))

    def fail(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(exporter.os, "replace", fail)
    assert not export.run_pass()
    # Neither a temporary file nor the liveness file.
    assert list(out.iterdir()) == []

    monkeypatch.undo()
    assert export.run_pass()
    assert manifests(out) == [NAME.format(1)]


def test_a_manifest_is_readable_by_others(db, export, out):
    """Created as an ordinary file is, under the umask, not tempfile's 0600: the
    service reading it may run as another user."""
    old = os.umask(0o022)
    try:
        arm_db.insert(db, "job", arm_db.job(1))
        export.run_pass()
    finally:
        os.umask(old)
    assert (out / NAME.format(1)).stat().st_mode & 0o777 == 0o644


def test_the_database_is_opened_read_only(db):
    con = connect(db, timeout=0.05)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        con.execute("INSERT INTO job (job_id) VALUES (1)")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        con.execute("CREATE TABLE x (y)")
    con.close()


def test_a_pass_leaves_the_database_alone(db, export):
    arm_db.insert(db, "job", arm_db.job(1))
    before = db.read_bytes(), db.stat().st_mtime_ns
    export.run_pass()
    assert (db.read_bytes(), db.stat().st_mtime_ns) == before
    assert sorted(p.name for p in db.parent.iterdir()) == ["arm.db", "manifests"]


def test_a_missing_database_is_not_created(tmp_path, out, caplog):
    missing = tmp_path / "nothing.db"
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert not Exporter(db=missing, out=out, root=ROOT, zone=UTC).run_pass()
    assert not missing.exists()
    assert "cannot read" in caplog.text
    assert list(out.iterdir()) == []


def test_a_missing_manifest_directory_is_not_created(db, tmp_path, caplog):
    out = tmp_path / "not-mounted"
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert not Exporter(db=db, out=out, root=ROOT, zone=UTC).run_pass()
    assert not out.exists()
    assert "does not exist" in caplog.text


def test_a_locked_database_is_retried_next_pass(db, export, out, caplog):
    arm_db.insert(db, "job", arm_db.job(1))
    writer = sqlite3.connect(db, autocommit=True)
    writer.execute("BEGIN EXCLUSIVE")
    writer.execute("UPDATE job SET status = 'ripping'")
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert not export.run_pass()
    assert "locked" in caplog.text
    # Nothing is written from a pass that couldn't read, liveness included,
    # so the liveness file's time means a pass that read the database.
    assert list(out.iterdir()) == []

    writer.execute("COMMIT")
    writer.close()
    assert export.run_pass()
    assert load(out, 1)["state"] == "running"


def test_a_job_that_cannot_be_exported_skips_only_itself(db, export, out, caplog):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.insert(db, "job", arm_db.job(2, start_time="not a time"))
    arm_db.insert(db, "job", arm_db.job(3))
    arm_db.insert(db, "reelbarrow_raw_copy", {"job_id": 3, "document": "{not json"})
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert export.run_pass()
    assert manifests(out) == [NAME.format(1)]
    assert "job 2 skipped" in caplog.text
    assert "job 3 skipped" in caplog.text
    assert json.loads((out / "exporter.json").read_text())["skipped_jobs"] == [2, 3]


def test_liveness_is_rewritten_each_pass(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1))
    export.run_pass()
    first = json.loads((out / "exporter.json").read_text())
    first_inode = (out / "exporter.json").stat().st_ino
    export.run_pass()
    second = json.loads((out / "exporter.json").read_text())

    assert (out / "exporter.json").stat().st_ino != first_inode
    assert second["passed_at"] >= first["passed_at"]
    assert second["passed_at"].endswith("+00:00")
    assert second["version"] == exporter.version("reelbarrow")
    assert second["jobs"] == 1
    assert second["skipped_jobs"] == []
    # Intake reads only manifests.
    assert manifests(out) == [NAME.format(1)]


def test_stale_temporaries_are_removed_at_start(out):
    (out / ".reelbarrow-manifest-arm-1-2.json.0123.tmp").write_text("{")
    (out / ".something-else.tmp").write_text("")
    (out / NAME.format(1)).write_text("{}")
    exporter.remove_stale_temporaries(out)
    assert sorted(p.name for p in out.iterdir()) == [
        ".something-else.tmp",
        NAME.format(1),
    ]


def test_the_command(db, out, monkeypatch, capsys):
    arm_db.insert(db, "job", arm_db.job(1))
    argv = [
        "reelbarrow",
        "export-manifests",
        "--db",
        str(db),
        "--out",
        str(out),
        "--arm-root",
        "/root/video=import/automatic-ripping-machine",
        "--arm-timezone",
        "Etc/UTC",
        "--once",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exit:
        cli.main()
    assert exit.value.code == 0
    assert manifests(out) == [NAME.format(1)]

    monkeypatch.setattr(sys, "argv", [*argv[:3], str(db.parent / "x.db"), *argv[4:]])
    with pytest.raises(SystemExit) as exit:
        cli.main()
    assert exit.value.code == 1

    for flag, bad in (
        ("--arm-timezone", "Mars/Olympus"),
        ("--arm-root", "/root/video"),
    ):
        wrong = list(argv)
        wrong[wrong.index(flag) + 1] = bad
        monkeypatch.setattr(sys, "argv", wrong)
        with pytest.raises(SystemExit) as exit:
            cli.main()
        assert exit.value.code == 2
