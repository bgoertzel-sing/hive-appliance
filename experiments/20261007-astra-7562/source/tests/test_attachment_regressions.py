"""Regression gates derived from Astra AF01-AF12."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from conversation.attachments import (
    AttachmentDownloadManager, AttachmentStore, SharedFolderManager,
)
from conversation.client import ConversationStoreClient
from conversation.collectors.telegram import TelegramEventCollector
from conversation.store import MessageStore
from conversation.types import Attachment, DownloadStatus, Message


class MemoryIndex:
    def __init__(self):
        self.messages = {}

    def index(self, messages):
        self.messages.update({message.id: message for message in messages})
        return len(messages)

    def search(self, query, **_kwargs):
        return [{"id": mid, "content": message.content, "distance": 0.0,
                 "metadata": {}} for mid, message in self.messages.items()]

    def count(self):
        return len(self.messages)


class Writer:
    def __init__(self, data=b"content", report_success=True, reported_size=None):
        self.data = data
        self.report_success = report_success
        self.reported_size = len(data) if reported_size is None else reported_size

    def get_file_info(self, _file_id):
        return {"file_size": self.reported_size}

    def download(self, _file_id, destination):
        if self.report_success:
            Path(destination).write_bytes(self.data)
        return True


def attachment(**updates):
    fields = dict(message_id="msg_parent", venue="telegram_group",
                  venue_id="-100", file_id="file-1", file_name="a.bin",
                  created_at=1_700_000_000.0)
    fields.update(updates)
    return Attachment(**fields)


def test_paths_are_root_contained(tmp_path):
    folder = SharedFolderManager(str(tmp_path / "root"))
    bad = attachment(id="/tmp/escape")
    with pytest.raises(ValueError):
        folder.resolve_path(bad)
    assert folder._sanitize("..") == "__"


def test_failed_batch_does_not_commit_prefix(tmp_path):
    store = AttachmentStore(str(tmp_path / "db.sqlite"))
    valid = attachment()
    invalid = attachment(file_id="file-2", metadata={"bad": object()})
    with pytest.raises(TypeError):
        store.append([valid, invalid])
    assert store.count() == 0


def test_claim_is_exclusive_and_expired_lease_recovers(tmp_path):
    path = str(tmp_path / "db.sqlite")
    first = AttachmentStore(path)
    second = AttachmentStore(path)
    first.append([attachment()])
    claim = first.claim_pending(1, lease_seconds=-1)
    assert len(claim) == 1
    recovered = second.claim_pending(1)
    assert len(recovered) == 1
    assert recovered[0].attempt_id != claim[0].attempt_id
    assert first.claim_pending(1) == []


def test_publication_requires_file_and_enforces_actual_size(tmp_path):
    store = AttachmentStore(str(tmp_path / "db.sqlite"))
    folder = SharedFolderManager(str(tmp_path / "files"))
    missing = AttachmentDownloadManager(store, folder, Writer(report_success=False))
    assert missing.enqueue(attachment())
    assert missing.process_pending()[0]["success"] is False
    assert store.get(attachment().id).download_status == DownloadStatus.FAILED

    oversized_att = attachment(file_id="file-2")
    oversized = AttachmentDownloadManager(
        store, folder, Writer(b"x" * 33, reported_size=0), max_file_size=32
    )
    assert oversized.enqueue(oversized_att)
    assert oversized.process_pending()[0]["success"] is False
    saved = store.get(oversized_att.id)
    assert saved.download_status == DownloadStatus.FAILED
    assert saved.local_path == ""
    assert not list(folder.base_dir.rglob("*.part"))


def test_missing_completed_file_is_reconciled(tmp_path):
    store = AttachmentStore(str(tmp_path / "db.sqlite"))
    folder = SharedFolderManager(str(tmp_path / "files"))
    manager = AttachmentDownloadManager(store, folder, Writer())
    item = attachment()
    assert manager.enqueue(item)
    assert manager.process_pending()[0]["success"]
    Path(store.get(item.id).local_path).unlink()
    assert manager.reconcile()["missing_completed"] == 1
    assert store.get(item.id).download_status == DownloadStatus.FAILED


def test_parent_coordinates_and_native_reply_survive_reopen(tmp_path):
    path = str(tmp_path / "db.sqlite")
    messages = MessageStore(path)
    parent = Message(venue="telegram_group", venue_id="-100",
                     venue_message_id="41", sender_id="u", content="file",
                     has_attachments=True)
    item = attachment(message_id=parent.id)
    parent.attachment_ids = [item.id]
    reply = Message(venue="telegram_group", venue_id="-100",
                    venue_message_id="42", sender_id="u2", content="reply",
                    reply_to_id="41")
    messages.append([parent, reply])
    attachments = AttachmentStore(path)
    assert attachments.append([item]) == 1
    reopened = MessageStore(path)
    restored = reopened.get(parent.id)
    assert restored.has_attachments
    assert restored.attachment_ids == [item.id]
    client = ConversationStoreClient(store=reopened, index=MemoryIndex())
    assert client.attachments_for_native_message("telegram_group", "-100", "41")[0].id == item.id
    assert client.attachments_for_reply(reply.id)[0].id == item.id


def test_structured_telegram_event_to_download_and_lookup(tmp_path):
    store = MessageStore(tmp_path / "db.sqlite")
    client = ConversationStoreClient(store=store, index=MemoryIndex())
    client.download_manager.set_downloader(Writer(b"telegram"))
    event = {
        "message_id": 7, "date": 1_700_000_000,
        "chat": {"id": -100, "type": "supergroup"},
        "from": {"id": 5, "username": "alice"},
        "caption": "report",
        "document": {
            "file_id": "token", "file_unique_id": "stable",
            "file_name": "report.pdf", "file_size": 8,
            "mime_type": "application/pdf",
        },
    }
    message, items = client.ingest_telegram_event(
        event, TelegramEventCollector(account_id="bot-a")
    )
    assert message.has_attachments and message.attachment_ids == [items[0].id]
    assert client.process_pending_downloads()[0]["success"]
    assert client.attachments_for_native_message(
        "telegram_group", "-100", "7"
    )[0].download_status == DownloadStatus.COMPLETED
