"""The registry under load: a busy database, and the transient errors SQLite gives when the machine is overloaded (a real session lost its
launch job to one: `backend_failed` from the registry, the run interrupted, every later call unavailable). Synthetic files only."""
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from src.errors import WorkbenchError
from src.registry import Registry


@pytest.fixture
def registry(tmp_path):
    root = tmp_path / "state"
    reg = Registry(root)
    reg.open()
    return reg


def write(reg):
    with reg._db(write=True) as db:
        db.execute("INSERT OR REPLACE INTO meta VALUES ('probe', 'x')")


def test_a_write_waits_out_a_lock_held_for_longer_than_five_seconds(registry):
    # The wait for a busy database was 5 seconds; a stalled machine kept the lock longer and the write failed as `busy`, which the
    # launch job did not survive. Heavy disk load is exactly when a registry write is slow.
    holder = sqlite3.connect(registry.path, isolation_level=None, check_same_thread=False)
    holder.execute("BEGIN IMMEDIATE")
    threading.Timer(6.5, lambda: holder.execute("COMMIT")).start()
    started = time.monotonic()
    write(registry)
    assert time.monotonic() - started >= 6.0
    holder.close()


class Flaky:
    """A connection whose first BEGIN fails the way an overloaded WAL database does (SQLITE_PROTOCOL: the WAL index lock was not taken)."""

    def __init__(self, real, failures, code):
        self.real, self.failures, self.code = real, failures, code

    def __getattr__(self, name):
        return getattr(self.real, name)

    @property
    def row_factory(self):
        return self.real.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self.real.row_factory = value

    def execute(self, sql, *args):
        if sql.startswith("BEGIN") and self.failures > 0:
            self.failures -= 1
            error = sqlite3.OperationalError("locking protocol")
            error.sqlite_errorcode = self.code
            raise error
        return self.real.execute(sql, *args)


@pytest.mark.parametrize("code", [15, 261, 517, 773, 5, 6])
def test_transient_sqlite_errors_are_retried_not_failed(registry, monkeypatch, code):
    real = sqlite3.connect
    attempts = []

    def connect(*args, **kwargs):
        attempts.append(1)
        return Flaky(real(*args, **kwargs), 2 if len(attempts) == 1 else 0, code)
    monkeypatch.setattr("src.registry.sqlite3.connect", connect)
    write(registry)
    assert len(attempts) >= 2


def test_an_error_that_is_not_transient_still_fails_without_a_retry(registry, monkeypatch):
    real = sqlite3.connect
    attempts = []

    def connect(*args, **kwargs):
        attempts.append(1)
        return Flaky(real(*args, **kwargs), 99, 10)    # SQLITE_IOERR
    monkeypatch.setattr("src.registry.sqlite3.connect", connect)
    with pytest.raises(WorkbenchError) as raised:
        write(registry)
    assert raised.value.envelope.code == "backend_failed" and len(attempts) == 1


# ---- opening the registry (every one-shot CLI call and every server start does it) while another process holds the write lock

def test_opening_an_initialized_registry_needs_no_write_lock(registry):
    # The open wrote (`INSERT OR IGNORE INTO meta`) with a 5 second wait, so a process that opened the registry while a slow writer held
    # it for longer failed with SQLite's raw "database is locked" (a one-shot `ls-wb call` printed `backend_failed`; found when a load
    # generator held a write transaction for 8 seconds while omp drove a session). An existing registry needs only reads to be opened.
    holder = sqlite3.connect(registry.path, isolation_level=None, check_same_thread=False)
    holder.execute("BEGIN IMMEDIATE")
    threading.Timer(6.5, lambda: holder.execute("COMMIT")).start()
    second = Registry(registry.state_root)
    started = time.monotonic()
    second.open()
    assert time.monotonic() - started < 2.0
    assert second.owner == registry.owner
    assert second.list_jobs(limit=5).jobs == []   # reads work while the writer holds the lock
    time.sleep(max(0.0, 6.7 - (time.monotonic() - started)))
    holder.close()


class FlakyOpen:
    """A connection whose first statements of the opening fail as an overloaded database does."""

    def __init__(self, real, plan):
        self.real, self.plan = real, plan

    def __getattr__(self, name):
        return getattr(self.real, name)

    def execute(self, sql, *args):
        if self.plan and sql.startswith(("PRAGMA journal_mode", "SELECT value FROM meta")):
            code = self.plan.pop(0)
            error = sqlite3.OperationalError("database is locked" if code in (5, 6) else "locking protocol")
            error.sqlite_errorcode = code
            raise error
        return self.real.execute(sql, *args)


@pytest.mark.parametrize("code", [5, 6, 15, 261, 517])
def test_a_transient_error_while_opening_is_retried(tmp_path, monkeypatch, code):
    reg = Registry(tmp_path / "state")
    reg.open()
    real = sqlite3.connect
    attempts = []

    def connect(*args, **kwargs):
        attempts.append(1)
        return FlakyOpen(real(*args, **kwargs), [code] if len(attempts) == 1 else [])
    monkeypatch.setattr("src.registry.sqlite3.connect", connect)
    second = Registry(tmp_path / "state")
    second.open()
    assert second.owner == reg.owner and len(attempts) >= 2


def test_opening_gives_up_as_busy_when_the_database_stays_locked(tmp_path, monkeypatch):
    reg = Registry(tmp_path / "state")
    reg.open()
    real = sqlite3.connect
    monkeypatch.setattr("src.registry.BUSY_SECONDS", 0.3)
    monkeypatch.setattr("src.registry.sqlite3.connect", lambda *a, **k: FlakyOpen(real(*a, **k), [5] * 1000))
    with pytest.raises(WorkbenchError) as raised:
        Registry(tmp_path / "state").open()
    assert raised.value.envelope.code == "busy" and raised.value.envelope.retryable


def test_an_opening_error_that_is_not_transient_fails_as_backend_failed(tmp_path, monkeypatch):
    reg = Registry(tmp_path / "state")
    reg.open()
    real = sqlite3.connect
    monkeypatch.setattr("src.registry.sqlite3.connect", lambda *a, **k: FlakyOpen(real(*a, **k), [10] * 1000))   # SQLITE_IOERR
    with pytest.raises(WorkbenchError) as raised:
        Registry(tmp_path / "state").open()
    assert raised.value.envelope.code == "backend_failed"
