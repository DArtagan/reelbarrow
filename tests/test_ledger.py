import sqlite3
from datetime import UTC, datetime

import cases
import pytest

from reelbarrow.ledger import FILE, Ledger, LedgerError, State
from reelbarrow.plan import plan

STARTED = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
FINISHED = datetime(2026, 11, 10, 12, 1, tzinfo=UTC)


@pytest.fixture
def case():
    return cases.load("dvd-film-raw-unrecorded")


@pytest.fixture
def made(case):
    return plan(case.manifest, case.analysis, case.tmdb, cases.Library())


@pytest.fixture
def manifest(case):
    return case.manifest


def test_an_entry_is_opened_updated_and_closed(tmp_path, manifest, made):
    ledger = Ledger(tmp_path)
    ledger.begin(manifest, made, STARTED, [{"outcome": "not_run"}])
    assert ledger.entry(made.source, made.id).state is State.STARTED

    ledger.update(made.source, made.id, [{"outcome": "done"}])
    ledger.update(made.source, made.id, [{"outcome": "done"}], State.FILED, FINISHED)

    entry = ledger.entry(made.source, made.id)
    assert entry.state is State.FILED
    assert (entry.started, entry.finished) == (STARTED, FINISHED)
    assert entry.outcomes == [{"outcome": "done"}]
    assert entry.plan == made.to_json()
    # The manifest as it was, which disc.json doesn't keep.
    assert entry.manifest == manifest.to_json()


def test_an_entry_is_one_units_manifest_and_plan(tmp_path, manifest, made):
    other = manifest.model_copy(update={"id": "35-1"})
    with pytest.raises(ValueError, match="35-1"):
        Ledger(tmp_path).begin(other, made, STARTED, [])


def test_a_unit_has_one_entry(tmp_path, manifest, made):
    ledger = Ledger(tmp_path)
    ledger.begin(manifest, made, STARTED, [])
    with pytest.raises(LedgerError, match="already in the ledger"):
        ledger.begin(manifest, made, STARTED, [])


def test_a_closed_entry_is_never_reopened(tmp_path, manifest, made):
    ledger = Ledger(tmp_path)
    ledger.begin(manifest, made, STARTED, [])
    ledger.update(made.source, made.id, [], State.FILED, FINISHED)
    with pytest.raises(LedgerError, match="no entry being filed"):
        ledger.update(made.source, made.id, [], State.INCOMPLETE, FINISHED)


def test_reading_a_ledger_that_isnt_there_makes_none(tmp_path):
    assert Ledger(tmp_path / "data").entry("arm", "1-1") is None
    assert not (tmp_path / "data").exists()


def test_reading_never_writes(tmp_path, manifest, made):
    Ledger(tmp_path).begin(manifest, made, STARTED, [])
    (tmp_path / FILE).chmod(0o444)
    assert Ledger(tmp_path).entry(made.source, made.id) is not None


def test_a_ledger_of_another_schema_is_refused(tmp_path):
    with sqlite3.connect(tmp_path / FILE) as connection:
        connection.execute("PRAGMA user_version = 7")
    with pytest.raises(LedgerError, match="schema 7"):
        Ledger(tmp_path).entry("arm", "1-1")
