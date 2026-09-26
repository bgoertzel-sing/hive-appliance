"""Tests for Astra re-review 6882 findings L1 (stop timeout) and S1 (status validation)."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from conversation.attachments import (
    AttachmentDownloadManager, AttachmentStore, SharedFolderManager,
)
from conversation.types import Attachment, DownloadStatus


def attachment(**updates):
    fields = dict(message_id="msg_parent", venue="telegram_group",
                  venue_id="-100", file_id="file-1", file_name="a.bin",
                  created_at=1_700_000_000.0)
    fields.update(updates)
    return Attachment(**fields)


class BlockingWriter:
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def get_file_info(self, _fid):
        return {"file_size": 4}

    def download(self, _fid, dest):
        self.entered.set()
        self.release.wait(10)
        Path(dest).write_bytes(b"data")
        return True


# ---------------------------------------------------------------- L1
def test_l1_attachment_stop_timeout_keeps_worker_and_refuses_restart(tmp_path):
    store = AttachmentStore(str(tmp_path / "db.sqlite"))
    folder = SharedFolderManager(str(tmp_path / "files"))
    w = BlockingWriter()
    mgr = AttachmentDownloadManager(store, folder, w)
    item = attachment()
    assert mgr.enqueue(item)
    mgr.start(poll_interval=0.01)
    assert w.entered.wait(5)
    old = mgr._worker
    assert mgr.stop(timeout=0.05) is False
    assert mgr._worker is old and old.is_alive()
    with pytest.raises(RuntimeError):
        mgr.start(poll_interval=0.01)
    assert mgr._worker is old  # no second worker spawned
    w.release.set()
    assert mgr.stop(timeout=5) is True
    assert mgr._worker is None
    assert store.get(item.id).download_status == DownloadStatus.COMPLETED
    mgr.start(poll_interval=0.01)  # clean restart now allowed
    assert mgr.stop(timeout=5) is True


def test_l1_hive_appliance_stop_timeout_refuses_restart():
    from hive.appliance import HiveAppliance
    app = HiveAppliance(poll_interval=0.01)
    entered, release = threading.Event(), threading.Event()

    def slow_tick():
        entered.set()
        release.wait(10)
        return {}

    app.tick = slow_tick
    app.run()
    assert entered.wait(5)
    old = app._thread
    assert app.stop(timeout=0.05) is False
    assert app._thread is old and old.is_alive()
    with pytest.raises(RuntimeError):
        app.run()
    assert app._thread is old
    release.set()
    assert app.stop(timeout=5) is True
    assert app._thread is None


# ---------------------------------------------------------------- S1
def _claimed(tmp_path):
    store = AttachmentStore(str(tmp_path / "db.sqlite"))
    item = attachment()
    assert store.append([item]) == 1
    claimed = store.claim_pending(1)[0]
    return store, item, claimed


@pytest.mark.parametrize("bad", ["pending", "downloading", "bogus", ""])
def test_s1_finish_attempt_rejects_non_terminal_status(tmp_path, bad):
    store, item, claimed = _claimed(tmp_path)
    with pytest.raises(ValueError):
        store.finish_attempt(item.id, claimed.attempt_id, bad)
    saved = store.get(item.id)
    assert saved.download_status == DownloadStatus.DOWNLOADING
    assert saved.attempt_id == claimed.attempt_id


def test_s1_finish_attempt_requires_attempt_id(tmp_path):
    store, item, _claimed_item = _claimed(tmp_path)
    with pytest.raises(ValueError):
        store.finish_attempt(item.id, "", DownloadStatus.FAILED)
    assert store.get(item.id).download_status == DownloadStatus.DOWNLOADING


def test_s1_finish_attempt_terminal_ok(tmp_path):
    store, item, claimed = _claimed(tmp_path)
    assert store.finish_attempt(item.id, claimed.attempt_id, DownloadStatus.FAILED, error="x")
    assert store.get(item.id).download_status == DownloadStatus.FAILED


def test_s1_db_rejects_invalid_status_new_table(tmp_path):
    store, item, _c = _claimed(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute("UPDATE attachments SET download_status='bogus' WHERE id=?", (item.id,))
    assert store.get(item.id).download_status == DownloadStatus.DOWNLOADING


def test_s1_db_rejects_invalid_status_legacy_table(tmp_path):
    db = str(tmp_path / "legacy.sqlite")
    c = sqlite3.connect(db)
    c.executescript("""
        CREATE TABLE attachments (
            id TEXT PRIMARY KEY, message_id TEXT NOT NULL, venue TEXT NOT NULL,
            venue_id TEXT NOT NULL, attachment_type TEXT NOT NULL DEFAULT 'unknown',
            file_id TEXT NOT NULL, file_unique_id TEXT NOT NULL DEFAULT '',
            file_name TEXT NOT NULL DEFAULT '', file_size INTEGER NOT NULL DEFAULT 0,
            mime_type TEXT NOT NULL DEFAULT '', local_path TEXT NOT NULL DEFAULT '',
            download_status TEXT NOT NULL DEFAULT 'pending',
            download_error TEXT NOT NULL DEFAULT '', thumbnail_path TEXT NOT NULL DEFAULT '',
            duration REAL, width INTEGER, height INTEGER,
            metadata TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL,
            downloaded_at REAL, schema_version TEXT NOT NULL DEFAULT '1');
        INSERT INTO attachments (id, message_id, venue, venue_id, file_id, created_at)
            VALUES ('att_x', 'm', 'telegram_group', '-1', 'f', 1.0);
    """)
    c.commit(); c.close()
    store = AttachmentStore(db)  # migration installs triggers
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute("UPDATE attachments SET download_status='bogus' WHERE id='att_x'")
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO attachments (id, message_id, venue, venue_id, file_id, created_at, download_status)"
            " VALUES ('att_y','m','telegram_group','-1','f',1.0,'weird')")
    row = store._conn.execute("SELECT download_status FROM attachments WHERE id='att_x'").fetchone()
    assert row[0] == "pending"
