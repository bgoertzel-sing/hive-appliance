"""Tests for conversation.attachments module."""
from __future__ import annotations

import os
import tempfile
import time

import pytest

from conversation.types import (
    Attachment,
    AttachmentType,
    DownloadStatus,
    Message,
    VenueType,
    _attachment_id,
)
from conversation.attachments import (
    AttachmentDownloadManager,
    AttachmentStore,
    SharedFolderManager,
)


# ── fixtures ─────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def store(tmp_dir):
    return AttachmentStore(db_path=os.path.join(tmp_dir, "test.db"))


@pytest.fixture
def folder(tmp_dir):
    return SharedFolderManager(base_dir=os.path.join(tmp_dir, "attachments"))


@pytest.fixture
def sample_attachment():
    return Attachment(
        message_id="msg_test123",
        venue=VenueType.TELEGRAM_GROUP,
        venue_id="-100999",
        attachment_type=AttachmentType.DOCUMENT,
        file_id="BQACAgIAAxkBAAtest",
        file_unique_id="AgADtest",
        file_name="report.pdf",
        file_size=1024000,
        mime_type="application/pdf",
    )


@pytest.fixture
def photo_attachment():
    return Attachment(
        message_id="msg_test456",
        venue=VenueType.TELEGRAM_GROUP,
        venue_id="-100999",
        attachment_type=AttachmentType.PHOTO,
        file_id="AgACAgIAAxkBAAphoto",
        file_unique_id="AQADphoto",
        file_name="image.jpg",
        file_size=50000,
        mime_type="image/jpeg",
        width=1920,
        height=1080,
    )


# ── _attachment_id ───────────────────────────────────────

class TestAttachmentId:
    def test_deterministic(self):
        a = _attachment_id("msg_1", "file_a")
        b = _attachment_id("msg_1", "file_a")
        assert a == b

    def test_prefix(self):
        assert _attachment_id("m", "f").startswith("att_")

    def test_different_inputs(self):
        a = _attachment_id("msg_1", "file_a")
        b = _attachment_id("msg_1", "file_b")
        assert a != b

    def test_length(self):
        aid = _attachment_id("msg_1", "file_a")
        assert len(aid) == 20  # att_ + 16 hex


# ── Attachment dataclass ─────────────────────────────────

class TestAttachment:
    def test_auto_id(self, sample_attachment):
        assert sample_attachment.id.startswith("att_")

    def test_validate_valid(self, sample_attachment):
        assert sample_attachment.validate() == []

    def test_validate_empty_id(self):
        att = Attachment()
        errors = att.validate()
        assert any("id" in e for e in errors)

    def test_validate_negative_size(self, sample_attachment):
        sample_attachment.file_size = -1
        errors = sample_attachment.validate()
        assert any("negative" in e for e in errors)

    def test_is_downloaded(self, sample_attachment):
        assert not sample_attachment.is_downloaded
        sample_attachment.download_status = DownloadStatus.COMPLETED
        assert sample_attachment.is_downloaded

    def test_extension_from_filename(self, sample_attachment):
        assert sample_attachment.extension == "pdf"

    def test_extension_from_mime(self):
        att = Attachment(
            message_id="msg_x", file_id="f1",
            mime_type="image/png",
        )
        assert att.extension == "png"

    def test_extension_fallback(self):
        att = Attachment(
            message_id="msg_x", file_id="f1",
            mime_type="application/octet-stream",
        )
        assert att.extension == "bin"

    def test_dict_roundtrip(self, sample_attachment):
        d = sample_attachment.to_dict()
        att2 = Attachment.from_dict(d)
        assert att2.id == sample_attachment.id
        assert att2.file_name == "report.pdf"
        assert att2.file_size == 1024000

    def test_dimensions(self, photo_attachment):
        assert photo_attachment.width == 1920
        assert photo_attachment.height == 1080


# ── SharedFolderManager ──────────────────────────────────

class TestSharedFolderManager:
    def test_resolve_path(self, folder, sample_attachment):
        path = folder.resolve_path(sample_attachment)
        assert "telegram_group" in path
        assert sample_attachment.id in path
        assert path.endswith(".pdf")

    def test_resolve_creates_dirs(self, folder, sample_attachment):
        path = folder.resolve_path(sample_attachment)
        assert os.path.isdir(os.path.dirname(path))

    def test_resolve_thumbnail_path(self, folder, sample_attachment):
        path = folder.resolve_thumbnail_path(sample_attachment)
        assert "thumbs" in path
        assert sample_attachment.id in path

    def test_disk_usage_empty(self, folder):
        usage = folder.disk_usage()
        assert usage["total_bytes"] == 0
        assert usage["file_count"] == 0

    def test_disk_usage_with_file(self, folder, sample_attachment):
        path = folder.resolve_path(sample_attachment)
        with open(path, "wb") as f:
            f.write(b"x" * 100)
        usage = folder.disk_usage()
        assert usage["total_bytes"] >= 100
        assert usage["file_count"] >= 1

    def test_sanitize(self):
        assert SharedFolderManager._sanitize("hello/world") == "hello_world"
        assert SharedFolderManager._sanitize("") == "unknown"
        assert len(SharedFolderManager._sanitize("a" * 200)) <= 100


# ── AttachmentStore ──────────────────────────────────────

class TestAttachmentStore:
    def test_append_and_get(self, store, sample_attachment):
        added = store.append([sample_attachment])
        assert added >= 1
        fetched = store.get(sample_attachment.id)
        assert fetched is not None
        assert fetched.file_name == "report.pdf"

    def test_dedup(self, store, sample_attachment):
        store.append([sample_attachment])
        store.append([sample_attachment])
        assert store.count() == 1

    def test_skip_invalid(self, store):
        invalid = Attachment()  # no id, no file_id
        added = store.append([invalid])
        assert added == 0

    def test_by_message(self, store, sample_attachment):
        store.append([sample_attachment])
        results = store.by_message(sample_attachment.message_id)
        assert len(results) == 1
        assert results[0].id == sample_attachment.id

    def test_by_venue(self, store, sample_attachment, photo_attachment):
        store.append([sample_attachment, photo_attachment])
        results = store.by_venue(venue=VenueType.TELEGRAM_GROUP)
        assert len(results) == 2

    def test_by_venue_with_type_filter(self, store, sample_attachment, photo_attachment):
        store.append([sample_attachment, photo_attachment])
        docs = store.by_venue(attachment_type=AttachmentType.DOCUMENT)
        assert len(docs) == 1
        assert docs[0].attachment_type == AttachmentType.DOCUMENT

    def test_pending_downloads(self, store, sample_attachment):
        store.append([sample_attachment])
        pending = store.pending_downloads()
        assert len(pending) == 1

    def test_update_status(self, store, sample_attachment):
        store.append([sample_attachment])
        store.update_status(
            sample_attachment.id,
            DownloadStatus.COMPLETED,
            local_path="/tmp/test.pdf",
            downloaded_at=time.time(),
        )
        fetched = store.get(sample_attachment.id)
        assert fetched.download_status == DownloadStatus.COMPLETED
        assert fetched.local_path == "/tmp/test.pdf"

    def test_count(self, store, sample_attachment, photo_attachment):
        store.append([sample_attachment, photo_attachment])
        assert store.count() == 2
        assert store.count(DownloadStatus.PENDING) == 2

    def test_stats(self, store, sample_attachment):
        store.append([sample_attachment])
        stats = store.stats()
        assert stats["total"] == 1
        assert stats["pending"] == 1
        assert stats["completed"] == 0


# ── AttachmentDownloadManager ────────────────────────────

class StubDownloader:
    """Test downloader that writes a small file."""

    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.downloads = []

    def download(self, file_id: str, dest_path: str) -> bool:
        self.downloads.append((file_id, dest_path))
        if self.should_fail:
            raise IOError("simulated failure")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(b"fake content")
        return True

    def get_file_info(self, file_id: str) -> dict:
        return {"file_id": file_id, "file_size": 100}


class TestAttachmentDownloadManager:
    def test_enqueue(self, store, folder, sample_attachment):
        mgr = AttachmentDownloadManager(store, folder)
        assert mgr.enqueue(sample_attachment)
        assert store.count() == 1

    def test_enqueue_oversized(self, store, folder):
        big = Attachment(
            message_id="msg_big",
            venue="tg",
            venue_id="123",
            attachment_type=AttachmentType.VIDEO,
            file_id="BIG",
            file_unique_id="BIG_U",
            file_size=100_000_000,
        )
        mgr = AttachmentDownloadManager(store, folder, max_file_size=50_000_000)
        mgr.enqueue(big)
        fetched = store.get(big.id)
        assert fetched.download_status == DownloadStatus.SKIPPED

    def test_process_without_downloader(self, store, folder, sample_attachment):
        mgr = AttachmentDownloadManager(store, folder)
        mgr.enqueue(sample_attachment)
        results = mgr.process_pending()
        assert results == []

    def test_process_success(self, store, folder, sample_attachment):
        dl = StubDownloader()
        mgr = AttachmentDownloadManager(store, folder, downloader=dl)
        mgr.enqueue(sample_attachment)
        results = mgr.process_pending()
        assert len(results) == 1
        assert results[0]["success"]
        assert len(dl.downloads) == 1
        fetched = store.get(sample_attachment.id)
        assert fetched.download_status == DownloadStatus.COMPLETED

    def test_process_failure(self, store, folder, sample_attachment):
        dl = StubDownloader(should_fail=True)
        mgr = AttachmentDownloadManager(store, folder, downloader=dl)
        mgr.enqueue(sample_attachment)
        results = mgr.process_pending()
        assert len(results) == 1
        assert not results[0]["success"]
        fetched = store.get(sample_attachment.id)
        assert fetched.download_status == DownloadStatus.FAILED

    def test_retry_failed(self, store, folder, sample_attachment):
        # First fail
        dl = StubDownloader(should_fail=True)
        mgr = AttachmentDownloadManager(store, folder, downloader=dl)
        mgr.enqueue(sample_attachment)
        mgr.process_pending()
        assert store.get(sample_attachment.id).download_status == DownloadStatus.FAILED
        # Now succeed on retry
        dl.should_fail = False
        results = mgr.retry_failed()
        assert len(results) == 1
        assert results[0]["success"]

    def test_set_downloader(self, store, folder, sample_attachment):
        mgr = AttachmentDownloadManager(store, folder)
        assert mgr.process_pending() == []
        dl = StubDownloader()
        mgr.set_downloader(dl)
        mgr.enqueue(sample_attachment)
        results = mgr.process_pending()
        assert len(results) == 1
        assert results[0]["success"]
