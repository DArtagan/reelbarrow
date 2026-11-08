"""ARM's database, copied out as one manifest per job.

`reelbarrow export-manifests` runs beside ARM, reads its SQLite database
read-only on an interval, and writes `job-<id>.json` for every job into the
manifest directory, which the service scans. *The ARM manifest* in the design
says why it polls rather than hooks a notification: ARM sets a job's final
status after its last notification, so only a reader that comes back later sees
it.

This module writes inside the output directory and nowhere else. It never
mounts the library; the executor's write rule allows it this one directory.
"""

import json
import logging
import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Raised when a field is removed or changes meaning, once reelbarrow's reader is
# deployed; a field added leaves it alone (the stamp's rule, in the design).
SCHEMA = 1
LIVENESS = "exporter.json"
# Hidden, and not matching job-*.json, so a scanner never picks up a file that
# is still being written.
TEMP_PREFIX = ".reelbarrow-"
TEMP_SUFFIX = ".tmp"


class SerialiseError(ValueError):
    """A value in a row that the manifest cannot carry faithfully."""


def connect(db: Path, timeout: float) -> sqlite3.Connection:
    """Open ARM's database for reading only.

    `mode=ro` makes SQLite refuse every write through this connection, whatever
    the mount allows. `timeout` is how long a read waits on ARM's write lock
    before giving up for this pass.
    """
    # mode=ro also refuses to create a missing file, so a wrong --db fails
    # rather than leaving an empty database behind.
    uri = f"{db.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=timeout, autocommit=True)


def _value(declared: str, value: Any, column: str) -> Any:
    """A column's value as JSON carries it, by the type SQLite declared for it.

    SQLAlchemy keeps booleans as 0/1 and datetimes as text with a space; they go
    out as true/false and ISO 8601. A datetime keeps the zone it was stored in,
    none for ARM, which stores its local time: converting it here would put the
    exporter's zone on ARM's clock.
    """
    if value is None:
        return None
    kind = declared.upper()
    if kind == "BOOLEAN":
        if value in (0, 1):
            return bool(value)
        raise SerialiseError(f"{column}: {value!r} is not a boolean")
    if kind in ("DATETIME", "TIMESTAMP"):
        try:
            return datetime.fromisoformat(value).isoformat()
        except (TypeError, ValueError) as error:
            raise SerialiseError(f"{column}: {value!r} is not a datetime") from error
    if isinstance(value, bytes):
        raise SerialiseError(f"{column}: a blob")
    if isinstance(value, float) and not math.isfinite(value):
        # JSON has no NaN or infinity; json.dumps would write invalid JSON.
        raise SerialiseError(f"{column}: {value}")
    return value


@dataclass(frozen=True, slots=True)
class Table:
    """A table's rows as ARM holds them, beside each column's declared type."""

    types: dict[str, str]
    rows: list[dict[str, Any]]

    def convert(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            name: _value(self.types.get(name, ""), value, name)
            for name, value in row.items()
        }


def _table(con: sqlite3.Connection, name: str, order: str) -> Table:
    """Every column of every row, in the table's own column order. Columns are
    not picked: ARM's migrations add them, and choosing now would guess at what
    a later spec needs."""
    types = {
        column: kind
        for _, column, kind, *_ in con.execute(f"PRAGMA table_info({name})")
    }
    cursor = con.execute(f"SELECT * FROM {name} ORDER BY {order}")
    names = [d[0] for d in cursor.description]
    return Table(types, [dict(zip(names, row, strict=True)) for row in cursor])


def read(con: sqlite3.Connection) -> tuple[Table, Table]:
    """The job and track tables, from one read transaction, so a manifest never
    mixes two states of a job. Never the config table: it holds ARM's API
    keys."""
    con.execute("BEGIN")
    try:
        return _table(con, "job", "job_id"), _table(con, "track", "job_id, track_id")
    finally:
        con.execute("ROLLBACK")


def manifest(
    jobs: Table, job: dict[str, Any], tracks: Table, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """The manifest of one job and its track rows. Raises SerialiseError for a
    value it can't carry."""
    return {
        "schema": SCHEMA,
        "job": jobs.convert(job),
        "tracks": [tracks.convert(row) for row in rows],
    }


def encode(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def write_atomically(out: Path, name: str, content: bytes) -> None:
    """Replace `out/name` with `content` so that a reader sees the old file or
    the new one, never part of either.

    The temporary file is created with mode 0666 less the umask, as an ordinary
    file would be, rather than tempfile's 0600, which a reader running as
    another user couldn't open.
    """
    temp = out / f"{TEMP_PREFIX}{name}.{uuid.uuid4().hex}{TEMP_SUFFIX}"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, out / name)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def remove_stale_temporaries(out: Path) -> None:
    """Remove temporary files a killed exporter left behind. Only this
    module's own, by their prefix and suffix."""
    for temp in out.glob(f"{TEMP_PREFIX}*{TEMP_SUFFIX}"):
        temp.unlink(missing_ok=True)


@dataclass
class Exporter:
    db: Path
    out: Path
    timeout: float = 5.0
    # Jobs whose row has gone while their manifest stays, logged once each.
    _gone: set[int] = field(default_factory=set)

    def run_pass(self) -> bool:
        """One pass: read the database, write the manifests that changed, then
        the liveness file. Returns whether it did all of that. Never raises for
        a database, row or share it can't read or write: it logs, and the next
        pass tries again."""
        if not self.out.is_dir():
            # Not created here: a missing mount would otherwise be filled
            # inside the container, and the service would see nothing.
            log.error("manifest directory %s does not exist", self.out)
            return False
        try:
            con = connect(self.db, self.timeout)
            try:
                jobs, tracks = read(con)
            finally:
                con.close()
        except sqlite3.Error as error:
            log.error("cannot read ARM's database %s: %s", self.db, error)
            return False

        try:
            self._export(jobs, tracks)
        except OSError as error:
            # The share, not the database. Liveness isn't written either, so a
            # share that stays unwritable reads as a stopped exporter.
            log.error("cannot write to %s: %s", self.out, error)
            return False
        return True

    def _export(self, jobs: Table, tracks: Table) -> None:
        by_job: dict[int, list[dict]] = {}
        for track in tracks.rows:
            by_job.setdefault(track["job_id"], []).append(track)

        written, skipped = 0, []
        for job in jobs.rows:
            job_id = job["job_id"]
            try:
                content = encode(manifest(jobs, job, tracks, by_job.get(job_id, [])))
            except SerialiseError as error:
                log.error("job %s skipped: %s", job_id, error)
                skipped.append(job_id)
                continue
            if self._write_if_changed(f"job-{job_id}.json", content):
                log.info("job %s: wrote manifest, status %s", job_id, job["status"])
                written += 1

        self._note_gone({job["job_id"] for job in jobs.rows})
        # Last, so its time is that of a pass that read the database and wrote
        # every manifest that changed.
        write_atomically(
            self.out,
            LIVENESS,
            encode(
                {
                    "passed_at": datetime.now(UTC).isoformat(),
                    "version": version("reelbarrow"),
                    "jobs": len(jobs.rows),
                    "skipped_jobs": skipped,
                }
            ),
        )
        log.debug("pass: %d jobs, %d written", len(jobs.rows), written)

    def _write_if_changed(self, name: str, content: bytes) -> bool:
        """An unchanged job leaves its file, and its modification time, alone,
        so the service's "manifest changed" is real."""
        try:
            if (self.out / name).read_bytes() == content:
                return False
        except FileNotFoundError:
            pass
        write_atomically(self.out, name, content)
        return True

    def _note_gone(self, present: set[int]) -> None:
        """A manifest outlives its row, deleted from ARM's UI or otherwise, and
        is never deleted here. Its row's absence is logged once."""
        on_disk = set()
        for path in self.out.glob("job-*.json"):
            try:
                on_disk.add(int(path.stem.removeprefix("job-")))
            except ValueError:
                continue
        for job_id in sorted(on_disk - present - self._gone):
            log.warning("job %s: row gone from ARM's database; manifest kept", job_id)
        self._gone = (self._gone | on_disk) - present

    def run(self, interval: float) -> None:
        """Pass after pass, `interval` seconds from the start of one to the
        start of the next, until killed. A kill mid-write leaves at most a
        temporary file, which the next start removes."""
        if self.out.is_dir():
            remove_stale_temporaries(self.out)
        while True:
            started = time.monotonic()
            self.run_pass()
            time.sleep(max(0.0, interval - (time.monotonic() - started)))
