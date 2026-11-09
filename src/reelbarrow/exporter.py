"""ARM's jobs, copied out of its database as manifests.

`reelbarrow arm-export-manifests` runs beside ARM, reads its SQLite database
read-only on an interval, and writes a manifest for every job into the
manifest directory, which the service scans. *The manifest* in the design says
why it polls rather than hooks a notification: ARM sets a job's final status
after its last notification, so only a reader that comes back later sees it.

This is the one place that knows ARM's schema. It reads the `job` row and the
deployment's raw-copy record (*The raw copy's record*), and translates both
into the manifest's vocabulary: ARM's statuses, its container's paths, its
local times and HandBrake's title numbers go no further.

It writes inside the output directory and nowhere else. It never mounts the
library; the executor's write rule allows it this one directory.
"""

import json
import logging
import os
import posixpath
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from reelbarrow import manifest
from reelbarrow.manifest import IdentityReason, Manifest, ShareRef, State

log = logging.getLogger(__name__)

SOURCE = "arm"
LIVENESS = "exporter.json"
# Hidden, and not matching the manifests' glob, so a scanner never picks up a
# file that is still being written.
TEMP_PREFIX = ".reelbarrow-"
TEMP_SUFFIX = ".tmp"

RAW_COPY_TABLE = "reelbarrow_raw_copy"
RAW_COPY_SCHEMA = 1
IDENTITY = {
    "title": "title",
    "year": "year",
    "imdb_id": "imdb_id",
    "kind": "video_type",
}
# The `job` columns read. One missing stops every pass: a manifest silently
# short of a field would read downstream as a fact not recorded.
COLUMNS = (
    "job_id",
    "stage",
    "status",
    "start_time",
    "stop_time",
    "errors",
    "disctype",
    "label",
    "crc_id",
    "path",
    "hasnicetitle",
    *(
        f"{column}{suffix}"
        for column in IDENTITY.values()
        for suffix in ("", "_auto", "_manual")
    ),
)
# What ARM writes where it has no value.
NO_VALUE = {None, "", "None"}
KINDS = {"movie", "series"}
FINAL = {"success": State.SUCCEEDED, "fail": State.FAILED}


class SerialiseError(ValueError):
    """A job the manifest cannot carry faithfully."""


class SchemaError(RuntimeError):
    """ARM's database lacks what the exporter reads."""


@dataclass(frozen=True, slots=True)
class ArmPath:
    """One folder, as ARM's container mounts it and as its path on the share.

    The share's path is what a manifest holds, so the exporter needs no one's
    mount but ARM's, and reelbarrow's service needs only its own.
    """

    arm: str
    share: str

    @classmethod
    def parse(cls, value: str) -> "ArmPath":
        """From `ARM=SHARE`: ARM's absolute path, and the share's path."""
        arm, sep, share = value.partition("=")
        if not sep or not posixpath.isabs(arm):
            raise ValueError(f"{value!r} is not ARM=SHARE, ARM's path absolute")
        share = share.rstrip("/")
        try:
            ShareRef(path=share)
        except ValidationError as error:
            raise ValueError(f"{share!r} is not a path on the share") from error
        return cls(posixpath.normpath(arm), share)

    def ref(self, path: str, what: str) -> dict:
        """ARM's path as a share reference. A path outside the folder mapped
        fails, rather than becoming a plausible wrong one."""
        normal = posixpath.normpath(path)
        if normal != path.rstrip("/") or not posixpath.isabs(normal):
            raise SerialiseError(f"{what} {path!r} is not a plain absolute path")
        relative = posixpath.relpath(normal, self.arm)
        if relative == ".." or relative.startswith("../"):
            raise SerialiseError(f"{what} {path!r} is outside {self.arm}")
        share = self.share if relative == "." else f"{self.share}/{relative}"
        try:
            return ShareRef(path=share).model_dump()
        except ValidationError as error:
            raise SerialiseError(f"{what}: {error}") from error


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


def read(con: sqlite3.Connection) -> tuple[list[dict], dict[int, str]]:
    """Every job and every raw-copy document, from one read transaction, so a
    manifest never mixes two states of a job. Never the config table: it holds
    ARM's API keys."""
    con.execute("BEGIN")
    try:
        present = {row[1] for row in con.execute("PRAGMA table_info(job)")}
        missing = [column for column in COLUMNS if column not in present]
        if missing:
            raise SchemaError(f"ARM's job table has no {', '.join(missing)}")
        cursor = con.execute(f"SELECT {', '.join(COLUMNS)} FROM job ORDER BY job_id")
        jobs = [dict(zip(COLUMNS, row, strict=True)) for row in cursor]
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master")}
        documents = (
            dict(con.execute(f"SELECT job_id, document FROM {RAW_COPY_TABLE}"))
            if RAW_COPY_TABLE in tables
            else {}
        )
    finally:
        con.execute("ROLLBACK")
    return jobs, documents


def _text(value: Any) -> str | None:
    return None if value in NO_VALUE else str(value)


def _time(value: Any, zone: ZoneInfo, column: str) -> str | None:
    """ARM's naive local time, in UTC with its offset."""
    if value is None:
        return None
    try:
        local = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise SerialiseError(f"{column}: {value!r} is not a datetime") from error
    if local.tzinfo is not None:
        raise SerialiseError(f"{column}: {value!r} has a zone ARM never writes")
    return local.replace(tzinfo=zone).astimezone(UTC).isoformat()


def _identity(job: dict) -> dict:
    """Each field with who supplied it.

    ARM's UI writes a `_manual` column for each field its form sets, and its
    lookup the `_auto` ones; the plain column is what ARM filed under. Two other
    writers leave no column of their own. ARM's series route sets `year`
    without `year_manual`, so on a job with a manual title a field that differs
    from ARM's lookup is a person's too. And `job_dupe_check`, finding one
    earlier successful job with the same disc label, copies its title, year
    and kind over whatever the lookup found, so on a job with no manual title
    such a field was copied.
    """
    corrected = _text(job["title_manual"]) is not None
    identity = {}
    for name, column in IDENTITY.items():
        value = _text(job[column])
        if name == "kind" and value not in KINDS:
            value = None
        found = _text(job[f"{column}_auto"])
        differs = value is not None and value != found
        if _text(job[f"{column}_manual"]) is not None or (corrected and differs):
            reason = IdentityReason.SET_BY_PERSON
        elif not job["hasnicetitle"]:
            # Before the copy: an unidentified job's title is its label, which
            # differs from the lookup that found nothing. job_dupe_check copies
            # `hasnicetitle` with the rest, so a copied identity still gets past.
            reason = IdentityReason.NOT_IDENTIFIED
        elif differs:
            reason = IdentityReason.COPIED_FROM_EARLIER_JOB
        else:
            reason = IdentityReason.LOOKUP
        identity[name] = {"value": value, "reason": reason}
    return identity


# A title's fields the record holds as the manifest does. Its paths are ARM's,
# translated, and its `handbrake_title` is the record's own key, dropped.
TITLE_FIELDS = ("disc_title", "playlist", "reason", "played_by", "interleaved", "parts")


def _title(entry: dict, root: ArmPath) -> dict:
    title = {name: entry[name] for name in TITLE_FIELDS if name in entry}
    if entry.get("extracted"):
        title["extracted"] = root.ref(entry["extracted"], "extracted title")
    if "transcode" in entry:
        transcode = entry["transcode"]
        title["transcode"] = transcode and root.ref(transcode, "transcode")
    return title


def _raw(document: dict, root: ArmPath) -> dict:
    """The raw copy's record as `raw` and `titles`. The record is in their
    shape already, so this only translates ARM's paths; the model checks the
    rest."""
    if document.get("schema") != RAW_COPY_SCHEMA:
        raise SerialiseError(f"raw copy schema {document.get('schema')!r}")
    raw = {
        "form": document["form"],
        "folder": root.ref(document["folder"], "raw folder"),
    }
    if document.get("image"):
        raw["image"] = root.ref(document["image"], "image")
    raw["check"] = document["check"]
    raw["problems"] = list(document.get("problems", []))
    if document.get("titles_compared"):
        raw["titles_compared"] = True
    out = {"raw": raw}
    if document.get("titles") is not None:
        out["titles"] = [_title(entry, root) for entry in document["titles"]]
    return out


def job_id(job: dict) -> str:
    """The manifest's id: a job id alone restarts with a recreated database,
    and the stage it was ripped at doesn't repeat."""
    if _text(job["stage"]) is None:
        raise SerialiseError("no stage")
    return f"{job['job_id']}-{job['stage']}"


def build(job: dict, document: str | None, root: ArmPath, zone: ZoneInfo) -> dict:
    """The manifest of one job, validated against the model. Raises
    SerialiseError for one it can't carry."""
    out = {
        "schema": manifest.SCHEMA,
        "source": SOURCE,
        "id": job_id(job),
        "state": FINAL.get(job["status"], State.RUNNING),
        "start_time": _time(job["start_time"], zone, "start_time"),
        "finish_time": _time(job["stop_time"], zone, "stop_time"),
        "errors": _text(job["errors"]),
        "disc": {
            "type": _text(job["disctype"]),
            "label": _text(job["label"]),
            "crc64": _text(job["crc_id"]),
        },
        "identity": _identity(job),
        "completed": None
        if _text(job["path"]) is None
        else {"folder": root.ref(job["path"], "completed folder")},
    }
    if document is not None:
        try:
            out |= _raw(json.loads(document), root)
        except SerialiseError:
            raise
        except (KeyError, TypeError, ValueError) as error:
            # A document of the right schema in the wrong shape.
            raise SerialiseError(f"raw copy: {error!r}") from error
    try:
        return Manifest.model_validate(out).to_json()
    except ValidationError as error:
        raise SerialiseError(f"not a valid manifest: {error}") from error


def encode(document: dict[str, Any]) -> bytes:
    # No NaN or infinity: JSON has neither, and json.dumps would write them.
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)
    return (text + "\n").encode()


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
    root: ArmPath
    zone: ZoneInfo
    timeout: float = 5.0
    # Manifests whose job's row has gone, logged once each.
    _gone: set[str] = field(default_factory=set)

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
                jobs, documents = read(con)
            finally:
                con.close()
        except (sqlite3.Error, SchemaError) as error:
            log.error("cannot read ARM's database %s: %s", self.db, error)
            return False
        try:
            self._export(jobs, documents)
        except OSError as error:
            # The share, not the database. Liveness isn't written either, so a
            # share that stays unwritable reads as a stopped exporter.
            log.error("cannot write to %s: %s", self.out, error)
            return False
        return True

    def _export(self, jobs: list[dict], documents: dict[int, str]) -> None:
        written, skipped, present = 0, [], set()
        for job in jobs:
            try:
                built = build(job, documents.get(job["job_id"]), self.root, self.zone)
            except SerialiseError as error:
                log.error("job %s skipped: %s", job["job_id"], error)
                skipped.append(job["job_id"])
                continue
            present.add(built["id"])
            name = manifest.filename(SOURCE, built["id"])
            if self._write_if_changed(name, encode(built)):
                log.info("job %s: wrote manifest, %s", job["job_id"], built["state"])
                written += 1

        self._note_gone(present)
        # Last, so its time is that of a pass that read the database and wrote
        # every manifest that changed.
        write_atomically(
            self.out,
            LIVENESS,
            encode(
                {
                    "passed_at": datetime.now(UTC).isoformat(),
                    "version": version("reelbarrow"),
                    "jobs": len(jobs),
                    "skipped_jobs": skipped,
                }
            ),
        )
        log.debug("pass: %d jobs, %d written", len(jobs), written)

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

    def _note_gone(self, present: set[str]) -> None:
        """A manifest outlives its row, deleted from ARM's UI or otherwise, and
        is never deleted here. Its row's absence is logged once."""
        prefix = manifest.filename(SOURCE, "")[: -len(".json")]
        on_disk = {
            path.name[len(prefix) : -len(".json")]
            for path in self.out.glob(f"{prefix}*.json")
        }
        for id in sorted(on_disk - present - self._gone):
            log.warning("job %s: row gone from ARM's database; manifest kept", id)
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
