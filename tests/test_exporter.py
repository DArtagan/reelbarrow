"""The exporter that copies ARM's database out as job manifests.

Against a database built from ARM 2.24.4's models (`arm_db`), with synthetic
rows. The manifest's shape is held by `fixtures/manifests/dvd-movie.json`; a
change to it brings a change to that fixture.
"""

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import arm_db
import pytest

from reelbarrow import cli, exporter
from reelbarrow.exporter import Exporter, connect


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
    return Exporter(db=db, out=out, timeout=0.05)


def manifests(out):
    return sorted(p.name for p in out.glob("job-*.json"))


def load(out, job_id):
    return json.loads((out / f"job-{job_id}.json").read_text())


def stat(out, job_id):
    st = (out / f"job-{job_id}.json").stat()
    return st.st_ino, st.st_mtime_ns


def test_manifest_shape(db, export, out, fixtures):
    arm_db.insert(db, "job", arm_db.job(7))
    arm_db.insert(db, "track", arm_db.track(31, 7))
    arm_db.insert(
        db,
        "track",
        arm_db.track(
            32,
            7,
            track_number="2",
            length=754,
            main_feature=0,
            filename="title_2.mkv",
            chapters=4,
            filesize=212860928,
        ),
    )
    assert export.run_pass()
    expected = (fixtures / "manifests" / "dvd-movie.json").read_text()
    assert (out / "job-7.json").read_text() == expected


def test_values_keep_their_meaning(db, export, out):
    arm_db.insert(
        db,
        "job",
        arm_db.job(
            1,
            status="active",
            stop_time=None,
            start_time="2026-10-21 19:49:49.000000",
            ejected=0,
        ),
    )
    arm_db.insert(db, "track", arm_db.track(1, 1, ripped=1, filename=""))
    export.run_pass()
    manifest = load(out, 1)
    job, (track,) = manifest["job"], manifest["tracks"]
    assert manifest["schema"] == 1
    # Booleans as booleans, null as null.
    assert job["ejected"] is False
    assert job["hasnicetitle"] is True
    assert job["stop_time"] is None
    # ISO 8601, in ARM's local time and so without a zone, never converted.
    assert job["start_time"] == "2026-10-21T19:49:49"
    # `ripped` passes through as ARM holds it: true with no transcode.
    assert track["ripped"] is True
    assert track["filename"] == ""


def test_every_column_goes_out(db, export, out):
    """No column is picked: one ARM adds in a migration is carried too."""
    arm_db.execute(db, "ALTER TABLE job ADD COLUMN some_new_column VARCHAR(8)")
    arm_db.execute(db, "ALTER TABLE track ADD COLUMN another BOOLEAN")
    arm_db.insert(db, "job", arm_db.job(1, some_new_column="x"))
    arm_db.insert(db, "track", arm_db.track(1, 1, another=0))
    export.run_pass()
    manifest = load(out, 1)
    assert list(manifest["job"]) == [*arm_db.job(1), "some_new_column"]
    assert manifest["job"]["some_new_column"] == "x"
    assert manifest["tracks"][0]["another"] is False


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


def test_a_pass_over_several_jobs(db, export, out):
    for job_id in (1, 2, 3):
        arm_db.insert(db, "job", arm_db.job(job_id))
    arm_db.insert(db, "track", arm_db.track(10, 1))
    arm_db.insert(db, "track", arm_db.track(11, 3, track_number="1"))
    arm_db.insert(db, "track", arm_db.track(12, 3, track_number="2"))
    assert export.run_pass()
    assert manifests(out) == ["job-1.json", "job-2.json", "job-3.json"]
    assert [t["track_id"] for t in load(out, 1)["tracks"]] == [10]
    assert load(out, 2)["tracks"] == []
    assert [t["track_id"] for t in load(out, 3)["tracks"]] == [11, 12]
    assert all(load(out, n)["job"]["job_id"] == n for n in (1, 2, 3))


def test_a_status_change_rewrites_only_that_job(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1, status="success"))
    arm_db.insert(db, "job", arm_db.job(2, status="ripping", stop_time=None))
    export.run_pass()
    before = stat(out, 1)

    arm_db.execute(db, "UPDATE job SET status = 'transcoding' WHERE job_id = 2")
    export.run_pass()
    assert load(out, 2)["job"]["status"] == "transcoding"
    assert stat(out, 1) == before

    arm_db.execute(
        db,
        "UPDATE job SET status = 'success', stop_time = ? WHERE job_id = 2",
        "2026-10-21 21:02:13.204518",
    )
    export.run_pass()
    assert load(out, 2)["job"]["status"] == "success"
    assert load(out, 2)["job"]["stop_time"] == "2026-10-21T21:02:13.204518"
    assert stat(out, 1) == before


def test_a_track_change_rewrites_its_job(db, export, out):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.insert(db, "track", arm_db.track(1, 1, filename=None, ripped=0))
    export.run_pass()
    arm_db.execute(db, "UPDATE track SET filename = 'title_1.mkv', ripped = 1")
    export.run_pass()
    assert load(out, 1)["tracks"][0]["filename"] == "title_1.mkv"


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
    kept = (out / "job-1.json").read_bytes()

    arm_db.execute(db, "DELETE FROM job WHERE job_id = 1")
    with caplog.at_level(logging.WARNING, logger="reelbarrow.exporter"):
        export.run_pass()
        export.run_pass()
    assert (out / "job-1.json").read_bytes() == kept
    assert manifests(out) == ["job-1.json", "job-2.json"]
    gone = [r for r in caplog.records if "row gone" in r.getMessage()]
    assert len(gone) == 1
    assert "job 1" in gone[0].getMessage()


def test_replacement_is_atomic(db, export, out, monkeypatch):
    """A reader sees the old file or the new one, never part of either: the new
    content is written whole beside the old, then renamed over it."""
    arm_db.insert(db, "job", arm_db.job(1, status="ripping"))
    export.run_pass()
    old = (out / "job-1.json").read_bytes()
    reader = open(out / "job-1.json", "rb")  # noqa: SIM115

    real_replace = os.replace
    seen = []

    def replace(src, dst):
        if str(dst).endswith("job-1.json"):
            # At the moment of the swap, the target is still whole, and the
            # temporary file is whole and invisible to a scan for job-*.json.
            assert (out / "job-1.json").read_bytes() == old
            json.loads(Path(src).read_bytes())
            assert os.path.basename(src).startswith(".")
            assert manifests(out) == ["job-1.json"]
            seen.append(src)
        real_replace(src, dst)

    monkeypatch.setattr(exporter.os, "replace", replace)
    arm_db.execute(db, "UPDATE job SET status = 'transcoding'")
    export.run_pass()

    assert len(seen) == 1
    assert load(out, 1)["job"]["status"] == "transcoding"
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
    assert manifests(out) == ["job-1.json"]


def test_a_manifest_is_readable_by_others(db, export, out):
    """Created as an ordinary file is, under the umask, not tempfile's 0600: the
    service reading it may run as another user."""
    old = os.umask(0o022)
    try:
        arm_db.insert(db, "job", arm_db.job(1))
        export.run_pass()
    finally:
        os.umask(old)
    assert (out / "job-1.json").stat().st_mode & 0o777 == 0o644


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
        assert not Exporter(db=missing, out=out).run_pass()
    assert not missing.exists()
    assert "cannot read" in caplog.text
    assert list(out.iterdir()) == []


def test_a_missing_manifest_directory_is_not_created(db, tmp_path, caplog):
    out = tmp_path / "not-mounted"
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert not Exporter(db=db, out=out).run_pass()
    assert not out.exists()
    assert "does not exist" in caplog.text


def test_a_locked_database_is_retried_next_pass(db, export, out, caplog):
    arm_db.insert(db, "job", arm_db.job(1))
    writer = sqlite3.connect(db, autocommit=True)
    writer.execute("BEGIN EXCLUSIVE")
    writer.execute("UPDATE job SET status = 'transcoding'")
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert not export.run_pass()
    assert "locked" in caplog.text
    # Nothing is written from a pass that couldn't read, liveness included,
    # so the liveness file's time means a pass that read the database.
    assert list(out.iterdir()) == []

    writer.execute("COMMIT")
    writer.close()
    assert export.run_pass()
    assert load(out, 1)["job"]["status"] == "transcoding"


def test_a_row_that_cannot_be_serialised_skips_only_its_job(db, export, out, caplog):
    arm_db.insert(db, "job", arm_db.job(1))
    arm_db.insert(db, "job", arm_db.job(2, start_time="not a time"))
    arm_db.insert(db, "job", arm_db.job(3))
    arm_db.insert(db, "track", arm_db.track(1, 3, ripped=7))
    with caplog.at_level(logging.ERROR, logger="reelbarrow.exporter"):
        assert export.run_pass()
    assert manifests(out) == ["job-1.json"]
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
    # Intake reads only job-*.json.
    assert manifests(out) == ["job-1.json"]


def test_stale_temporaries_are_removed_at_start(out):
    (out / ".reelbarrow-job-1.json.0123.tmp").write_text("{")
    (out / ".something-else.tmp").write_text("")
    (out / "job-1.json").write_text("{}")
    exporter.remove_stale_temporaries(out)
    assert sorted(p.name for p in out.iterdir()) == [
        ".something-else.tmp",
        "job-1.json",
    ]


def test_the_command(db, out, monkeypatch):
    arm_db.insert(db, "job", arm_db.job(1))
    argv = ["reelbarrow", "export-manifests", "--db", str(db), "--out", str(out)]
    monkeypatch.setattr(sys, "argv", [*argv, "--once"])
    with pytest.raises(SystemExit) as exit:
        cli.main()
    assert exit.value.code == 0
    assert manifests(out) == ["job-1.json"]

    monkeypatch.setattr(
        sys, "argv", [*argv[:3], str(db.parent / "x.db"), *argv[4:], "--once"]
    )
    with pytest.raises(SystemExit) as exit:
        cli.main()
    assert exit.value.code == 1
