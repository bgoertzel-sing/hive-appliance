"""Tests for Astra re-review 6882 findings A1, A2, P1-symlink, P2-store."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from conversation.attachments import (
    AttachmentDownloadManager, AttachmentStore, SharedFolderManager,
)
from conversation.types import Attachment, DownloadStatus


class Writer:
    def __init__(self, data=b"content"):
        self.data = data

    def get_file_info(self, _file_id):
        return {"file_size": len(self.data)}

    def download(self, _file_id, destination):
        Path(destination).write_bytes(self.data)
        return True


def attachment(**updates):
    fields = dict(message_id="msg_parent", venue="telegram_group",
                  venue_id="-100", file_id="file-1", file_name="a.bin",
                  created_at=1_700_000_000.0)
    fields.update(updates)
    return Attachment(**fields)


def _setup(tmp_path, data=b"content"):
    db = str(tmp_path / "db.sqlite")
    store = AttachmentStore(db)
    folder = SharedFolderManager(str(tmp_path / "files"))
    return db, store, folder, AttachmentDownloadManager(store, folder, Writer(data))


# ---------------------------------------------------------------- A1
def test_a1_losing_attempt_does_not_unlink_winner(tmp_path):
    db, store, folder, mgr = _setup(tmp_path)
    item = attachment()
    assert mgr.enqueue(item)
    loser = store.claim_pending(1, lease_seconds=-1)[0]      # lease expires at once
    winner = AttachmentStore(db).claim_pending(1)[0]         # re-claimed
    assert winner.attempt_id != loser.attempt_id

    assert mgr._download_one(winner)["success"] is True
    win_path = Path(store.get(item.id).local_path)
    assert win_path.is_file()

    res = mgr._download_one(loser)
    assert res["success"] is False

    saved = store.get(item.id)
    assert saved.download_status == DownloadStatus.COMPLETED
    assert saved.attempt_id == winner.attempt_id
    assert Path(saved.local_path) == win_path and win_path.read_bytes() == b"content"
    # the loser left nothing behind
    files = [p for p in folder.base_dir.rglob("*") if p.is_file()]
    assert files == [win_path]


def test_a1_artifact_paths_are_attempt_specific(tmp_path):
    folder = SharedFolderManager(str(tmp_path / "files"))
    canon = folder.resolve_path(attachment())
    a = folder.attempt_artifact_path(canon, "aaa")
    b = folder.attempt_artifact_path(canon, "bbb")
    assert a != b and a.parent == b.parent == Path(canon).parent
    with pytest.raises(ValueError):
        folder.attempt_artifact_path(canon, "../x")
    with pytest.raises(ValueError):
        folder.attempt_artifact_path(canon, "")


# ---------------------------------------------------------------- A2
def test_a2_reconcile_keeps_active_partials_removes_orphans(tmp_path):
    db, store, folder, mgr = _setup(tmp_path)
    item = attachment()
    assert mgr.enqueue(item)
    live = store.claim_pending(1, lease_seconds=300)[0]
    canon = folder.resolve_path(live)
    final = folder.attempt_artifact_path(canon, live.attempt_id)
    active_part = final.with_name(f".{final.name}.{live.attempt_id}.part")
    active_part.write_bytes(b"half")
    orphan = final.with_name(f".{final.name}.deadbeef.part")
    orphan.write_bytes(b"old")

    rep = mgr.reconcile()

    assert active_part.is_file(), "in-flight partial must survive reconcile"
    assert not orphan.exists()
    assert rep["orphan_partials"] == 1 and rep["active_partials_kept"] == 1
    # the live lease itself was not reset
    assert store.get(item.id).download_status == DownloadStatus.DOWNLOADING
    assert store.get(item.id).attempt_id == live.attempt_id


def test_a2_reconcile_does_not_follow_symlinked_dirs(tmp_path):
    _db, _store, folder, mgr = _setup(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / ".victim.x.part"
    victim.write_bytes(b"keep")
    folder.base_dir.mkdir(parents=True, exist_ok=True)
    os.symlink(outside, folder.base_dir / "link")
    mgr.reconcile()
    assert victim.is_file()


# ---------------------------------------------------------------- P2
def test_p2_delete_refuses_uncontained_path(tmp_path):
    root = tmp_path / "files"
    store = AttachmentStore(str(tmp_path / "db.sqlite"), attachments_root=str(root))
    victim = tmp_path / "victim.txt"
    victim.write_text("precious")
    item = attachment(local_path=str(victim))
    assert store.append([item]) == 1
    assert store.delete(item.id) is True
    assert victim.read_text() == "precious"
    assert store.get(item.id) is None


def test_p2_delete_without_root_never_unlinks(tmp_path):
    store = AttachmentStore(str(tmp_path / "db.sqlite"))
    victim = tmp_path / "v.txt"
    victim.write_text("x")
    item = attachment(local_path=str(victim))
    store.append([item])
    store.delete(item.id)
    assert victim.exists()


def test_p2_delete_refuses_symlink_inside_root(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    victim = tmp_path / "v.txt"
    victim.write_text("x")
    link = root / "evil.bin"
    os.symlink(victim, link)
    store = AttachmentStore(str(tmp_path / "db.sqlite"), attachments_root=str(root))
    item = attachment(local_path=str(link))
    store.append([item])
    store.delete(item.id)
    assert victim.exists() and link.is_symlink()


def test_p2_delete_removes_contained_file(tmp_path):
    _db, store, folder, mgr = _setup(tmp_path)
    item = attachment()
    mgr.enqueue(item)
    assert mgr.process_pending()[0]["success"]
    path = Path(store.get(item.id).local_path)
    assert path.is_file()
    assert store.delete(item.id, folder=folder)
    assert not path.exists()


def test_p2_publish_ignores_stored_uncontained_local_path(tmp_path):
    _db, store, folder, mgr = _setup(tmp_path)
    evil = tmp_path / "evil_target.bin"
    item = attachment(local_path=str(evil))
    # enqueue() already rejects uncontained paths ...
    assert mgr.enqueue(item) is False
    # ... but a row written directly to the store must not be trusted either.
    assert store.append([item]) == 1
    assert mgr.process_pending()[0]["success"]
    saved = Path(store.get(item.id).local_path)
    assert not evil.exists()
    assert folder.contains(str(saved)) and saved.is_file()


# ---------------------------------------------------------------- P1
def test_p1_symlinked_venue_dir_rejected_before_mkdir(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, root / "telegram_group")
    folder = SharedFolderManager(str(root))
    with pytest.raises(ValueError):
        folder.resolve_path(attachment())
    assert list(outside.iterdir()) == [], "nothing may be created outside root"


def test_p1_symlinked_root_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "rootlink"
    os.symlink(real, link)
    folder = SharedFolderManager(str(link))
    # Path.resolve() in __init__ canonicalizes the root; files must stay in real/
    p = Path(folder.resolve_path(attachment()))
    assert real in p.parents
