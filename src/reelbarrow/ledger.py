"""The ledger: what was filed, from which plan, and what each operation did.

Once a file has moved, the ledger and the library's `disc.json` are the only
record of where it came from (*The manifest*, in the design), so the ledger is
written as the filing goes rather than once at its end. Its entry is opened
before the first operation and updated after each, so a filing that dies
part way leaves an entry that says how far it got. An entry is keyed by its
manifest's `source` and `id`, and there is one a unit: a unit with an entry
is never filed again by a fresh plan.

It is SQLite under `REELBARROW_DATA_DIR`, never on the share. Dry run doesn't
write it: a unit nothing was done to isn't filed.
"""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict

from reelbarrow.plan import Plan

FILE = "reelbarrow.sqlite3"
SCHEMA = 1

_CREATE = """
CREATE TABLE filing (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('started', 'incomplete', 'filed')),
    started TEXT NOT NULL,
    finished TEXT,
    version TEXT NOT NULL,
    plan TEXT NOT NULL,
    outcomes TEXT NOT NULL,
    PRIMARY KEY (source, id)
) STRICT
"""


class State(StrEnum):
    # Operations under way, or the process died while they were.
    STARTED = "started"
    # An operation failed, and the rest weren't attempted.
    INCOMPLETE = "incomplete"
    FILED = "filed"


class Entry(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    id: str
    state: State
    started: AwareDatetime
    finished: AwareDatetime | None
    version: str
    plan: dict
    outcomes: list[dict]


class LedgerError(Exception):
    """The ledger can't be read or written as this version keeps it."""


class Ledger:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / FILE

    def _connect(self, *, write: bool) -> sqlite3.Connection:
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Autocommit: each statement is durable as it returns.
            connection = sqlite3.connect(self.path, isolation_level=None)
        else:
            connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        connection.execute("PRAGMA busy_timeout = 5000")
        found = connection.execute("PRAGMA user_version").fetchone()[0]
        if write and found == 0:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("PRAGMA user_version").fetchone()[0] == 0:
                connection.execute(_CREATE)
                connection.execute(f"PRAGMA user_version = {SCHEMA}")
            connection.execute("COMMIT")
            found = SCHEMA
        if found != SCHEMA:
            connection.close()
            raise LedgerError(f"{self.path} is schema {found}, not {SCHEMA}")
        return connection

    def entry(self, source: str, id: str) -> Entry | None:
        """A unit's entry, read without creating the ledger."""
        if not self.path.exists():
            return None
        with closing(self._connect(write=False)) as connection:
            row = connection.execute(
                "SELECT source, id, state, started, finished, version, plan, outcomes"
                " FROM filing WHERE source = ? AND id = ?",
                (source, id),
            ).fetchone()
        if row is None:
            return None
        keys = ("source", "id", "state", "started", "finished", "version")
        return Entry(
            **dict(zip(keys, row[:6], strict=True)),
            plan=json.loads(row[6]),
            outcomes=json.loads(row[7]),
        )

    def begin(self, plan: Plan, started: datetime, outcomes: list[dict]) -> None:
        """Opens a unit's entry; refused if it has one."""
        with closing(self._connect(write=True)) as connection:
            try:
                connection.execute(
                    "INSERT INTO filing VALUES (?, ?, ?, ?, NULL, ?, ?, ?)",
                    (
                        plan.source,
                        plan.id,
                        State.STARTED.value,
                        started.isoformat(),
                        version("reelbarrow"),
                        json.dumps(plan.to_json(), ensure_ascii=False),
                        json.dumps(outcomes, ensure_ascii=False),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise LedgerError(
                    f"{plan.source} {plan.id} is already in the ledger"
                ) from error

    def update(
        self,
        source: str,
        id: str,
        outcomes: list[dict],
        state: State = State.STARTED,
        finished: datetime | None = None,
    ) -> None:
        with closing(self._connect(write=True)) as connection:
            changed = connection.execute(
                "UPDATE filing SET outcomes = ?, state = ?, finished = ?"
                " WHERE source = ? AND id = ? AND state = 'started'",
                (
                    json.dumps(outcomes, ensure_ascii=False),
                    state.value,
                    finished.isoformat() if finished else None,
                    source,
                    id,
                ),
            ).rowcount
        if changed != 1:
            raise LedgerError(f"{source} {id} has no entry being filed")
