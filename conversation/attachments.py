"""
AttachmentStore — SQLite-backed storage and download management for attachments.

Provides:
- Durable metadata storage (SQLite, same DB as MessageStore)
- Shared folder organization (by venue/date)
- Download queue management
- Attachment queries by message, venue, type, status
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from conversation.types import (
    Attachment,
    AttachmentType,
    DownloadStatus,
)

logger = logging.getLogger(__name__)

# ── defaults ─────────────────────────────────────────────

DEFAULT_DB_PATH = "/hive/shared/conversation-store/messages.db"
DEFAULT_ATTACHMENTS_DIR = "/hive/shared/conversation-store/attachments"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB default max download size


# ── downloader protocol ─────────────────────────────────

@runtime_checkable
class AttachmentDownloader(Protocol):
    """Protocol for platform-specific file downloaders.

    Implementations handle the actual download from Telegram, Slack, etc.
    """

    def download(self, file_id: str, dest_path: str) -> bool:
        """Download file_id to dest_path. Returns True on success."""
        ...

    def get_file_info(self, file_id: str) -> dict[str, Any]:
        """Get file metadata (size, mime_type, etc.) without downloading."""
        ...


# ── shared folder manager ────────────────────────────────

class SharedFolderManager:
    """Organizes downloaded attachments in a shared folder structure.

    Layout:
        {base_dir}/{venue_type}/{venue_id}/{YYYY-MM-DD}/{attachment_id}.{ext}

    Thread-safe: uses a lock for directory creation.
    """

    def __init__(self, base_dir: str = DEFAULT_ATTACHMENTS_DIR):
        self._base_dir = Path(base_dir)
        self._lock = threading.Lock()

    @property
    def base_dir(self) -> Path:
        """Return base dir."""
        return self._base_dir

    def resolve_path(self, attachment: Attachment) -> str:
        """Compute the local storage path for an attachment.

        Creates intermediate directories as needed.
        """
        # Determine date from attachment creation time
        dt = datetime.fromtimestamp(attachment.created_at, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")

        # Sanitize venue components for filesystem safety
        venue = self._sanitize(attachment.venue or "unknown")
        venue_id = self._sanitize(attachment.venue_id or "unknown")

        # Build path
        dir_path = self._base_dir / venue / venue_id / date_str

        # Filename: attachment_id.extension
        filename = f"{attachment.id}.{attachment.extension}"

        with self._lock:
            dir_path.mkdir(parents=True, exist_ok=True)

        return str(dir_path / filename)

    def resolve_thumbnail_path(self, attachment: Attachment) -> str:
        """Compute thumbnail storage path."""
        dt = datetime.fromtimestamp(attachment.created_at, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        venue = self._sanitize(attachment.venue or "unknown")
        venue_id = self._sanitize(attachment.venue_id or "unknown")
        dir_path = self._base_dir / venue / venue_id / date_str / "thumbs"

        with self._lock:
            dir_path.mkdir(parents=True, exist_ok=True)

        return str(dir_path / f"{attachment.id}_thumb.jpg")

    def disk_usage(self) -> dict[str, Any]:
        """Report disk usage of the attachments folder."""
        total_size = 0
        file_count = 0
        for dirpath, _dirnames, filenames in os.walk(self._base_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                    file_count += 1
                except OSError:
                    pass
        return {
            "total_bytes": total_size,
            "total_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "base_dir": str(self._base_dir),
        }

    @staticmethod
    def _sanitize(name: str) -> str:
        """Sanitize a string for use as a directory/file name."""
        # Replace unsafe chars with underscore
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        return safe[:100] or "unknown"  # Cap length


# ── attachment store ─────────────────────────────────────

class AttachmentStore:
    """SQLite-backed attachment metadata store.

    Uses the same database as MessageStore (shared SQLite file) with a
    separate 'attachments' table. Thread-safe via thread-local connections.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema(self._conn)

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS attachments (
                id              TEXT PRIMARY KEY,
                message_id      TEXT NOT NULL,
                venue           TEXT NOT NULL,
                venue_id        TEXT NOT NULL,
                attachment_type TEXT NOT NULL DEFAULT 'unknown',
                file_id         TEXT NOT NULL,
                file_unique_id  TEXT NOT NULL DEFAULT '',
                file_name       TEXT NOT NULL DEFAULT '',
                file_size       INTEGER NOT NULL DEFAULT 0,
                mime_type       TEXT NOT NULL DEFAULT '',
                local_path      TEXT NOT NULL DEFAULT '',
                download_status TEXT NOT NULL DEFAULT 'pending',
                download_error  TEXT NOT NULL DEFAULT '',
                thumbnail_path  TEXT NOT NULL DEFAULT '',
                duration        REAL,
                width           INTEGER,
                height          INTEGER,
                metadata        TEXT NOT NULL DEFAULT '{}',
                created_at      REAL NOT NULL,
                downloaded_at   REAL,
                schema_version  TEXT NOT NULL DEFAULT '1'
            );

            CREATE INDEX IF NOT EXISTS idx_attachments_message
                ON attachments(message_id);
            CREATE INDEX IF NOT EXISTS idx_attachments_venue
                ON attachments(venue, venue_id);
            CREATE INDEX IF NOT EXISTS idx_attachments_status
                ON attachments(download_status);
            CREATE INDEX IF NOT EXISTS idx_attachments_type
                ON attachments(attachment_type);
        """)
        conn.commit()

    # ── write operations ─────────────────────────────────

    def append(self, attachments: list[Attachment]) -> int:
        """Insert attachments, deduplicating on ID. Returns count added."""
        if not attachments:
            return 0

        added = 0
        conn = self._conn
        for att in attachments:
            errors = att.validate()
            if errors:
                logger.warning("Skipping invalid attachment %s: %s", att.id, errors)
                continue
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO attachments
                       (id, message_id, venue, venue_id, attachment_type,
                        file_id, file_unique_id, file_name, file_size,
                        mime_type, local_path, download_status, download_error,
                        thumbnail_path, duration, width, height,
                        metadata, created_at, downloaded_at, schema_version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        att.id, att.message_id, att.venue, att.venue_id,
                        att.attachment_type, att.file_id, att.file_unique_id,
                        att.file_name, att.file_size, att.mime_type,
                        att.local_path, att.download_status, att.download_error,
                        att.thumbnail_path, att.duration, att.width, att.height,
                        json.dumps(att.metadata), att.created_at,
                        att.downloaded_at, att.schema_version,
                    ),
                )
                if conn.total_changes:
                    added += 1
            except sqlite3.Error:
                logger.exception("Error inserting attachment %s", att.id)
        conn.commit()
        return added

    def update_status(
        self,
        attachment_id: str,
        status: str,
        local_path: str = "",
        error: str = "",
        downloaded_at: Optional[float] = None,
    ) -> bool:
        """Update download status for an attachment."""
        conn = self._conn
        try:
            conn.execute(
                """UPDATE attachments
                   SET download_status = ?, local_path = ?,
                       download_error = ?, downloaded_at = ?
                   WHERE id = ?""",
                (status, local_path, error, downloaded_at, attachment_id),
            )
            conn.commit()
            return conn.total_changes > 0
        except sqlite3.Error:
            logger.exception("Error updating attachment status %s", attachment_id)
            return False

    # ── query operations ─────────────────────────────────

    def get(self, attachment_id: str) -> Optional[Attachment]:
        """Get a single attachment by ID."""
        row = self._conn.execute(
            "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        return self._row_to_attachment(row) if row else None

    def by_message(self, message_id: str) -> list[Attachment]:
        """Get all attachments for a message."""
        rows = self._conn.execute(
            "SELECT * FROM attachments WHERE message_id = ? ORDER BY created_at",
            (message_id,),
        ).fetchall()
        return [self._row_to_attachment(r) for r in rows]

    def by_venue(
        self,
        venue: str = "",
        venue_id: str = "",
        limit: int = 100,
        attachment_type: str = "",
    ) -> list[Attachment]:
        """Query attachments by venue, optionally filtered by type."""
        conditions: list[str] = []
        params: list[Any] = []
        if venue:
            conditions.append("venue = ?")
            params.append(venue)
        if venue_id:
            conditions.append("venue_id = ?")
            params.append(venue_id)
        if attachment_type:
            conditions.append("attachment_type = ?")
            params.append(attachment_type)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM attachments WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_attachment(r) for r in rows]

    def pending_downloads(self, limit: int = 50) -> list[Attachment]:
        """Get attachments awaiting download."""
        rows = self._conn.execute(
            """SELECT * FROM attachments
               WHERE download_status = 'pending'
               ORDER BY created_at ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_attachment(r) for r in rows]

    def count(self, status: str = "") -> int:
        """Count attachments, optionally filtered by status."""
        if status:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM attachments WHERE download_status = ?",
                (status,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM attachments").fetchone()
        return row[0] if row else 0

    def stats(self) -> dict[str, Any]:
        """Return attachment statistics."""
        total = self.count()
        completed = self.count(DownloadStatus.COMPLETED)
        pending = self.count(DownloadStatus.PENDING)
        failed = self.count(DownloadStatus.FAILED)
        # Total downloaded size
        row = self._conn.execute(
            "SELECT COALESCE(SUM(file_size), 0) FROM attachments WHERE download_status = 'completed'"
        ).fetchone()
        downloaded_bytes = row[0] if row else 0
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "skipped": self.count(DownloadStatus.SKIPPED),
            "downloaded_bytes": downloaded_bytes,
            "downloaded_mb": round(downloaded_bytes / (1024 * 1024), 2),
        }

    # ── helpers ──────────────────────────────────────────

    def _row_to_attachment(self, row: sqlite3.Row) -> Attachment:
        """Convert a database row to an Attachment dataclass."""
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        return Attachment(
            id=row["id"],
            message_id=row["message_id"],
            venue=row["venue"],
            venue_id=row["venue_id"],
            attachment_type=row["attachment_type"],
            file_id=row["file_id"],
            file_unique_id=row["file_unique_id"],
            file_name=row["file_name"],
            file_size=row["file_size"],
            mime_type=row["mime_type"],
            local_path=row["local_path"],
            download_status=row["download_status"],
            download_error=row["download_error"],
            thumbnail_path=row["thumbnail_path"],
            duration=row["duration"],
            width=row["width"],
            height=row["height"],
            metadata=meta,
            created_at=row["created_at"],
            downloaded_at=row["downloaded_at"],
            schema_version=row["schema_version"],
        )


# ── download manager ─────────────────────────────────────

class AttachmentDownloadManager:
    """Manages the download queue for attachments.

    Coordinates between AttachmentStore (metadata), SharedFolderManager
    (file paths), and AttachmentDownloader (actual downloads).

    Usage:
        manager = AttachmentDownloadManager(store, folder, downloader)
        manager.enqueue(attachment)           # register for download
        results = manager.process_pending()   # download pending items
    """

    def __init__(
        self,
        store: AttachmentStore,
        folder: SharedFolderManager,
        downloader: Optional[AttachmentDownloader] = None,
        max_file_size: int = MAX_FILE_SIZE,
    ):
        self._store = store
        self._folder = folder
        self._downloader = downloader
        self._max_file_size = max_file_size
        self._lock = threading.Lock()

    def set_downloader(self, downloader: AttachmentDownloader) -> None:
        """Set or replace the platform downloader."""
        self._downloader = downloader

    def enqueue(self, attachment: Attachment) -> bool:
        """Register an attachment for download.

        Returns True if successfully enqueued (or already exists).
        """
        # Check file size limit
        if attachment.file_size > self._max_file_size > 0:
            logger.info(
                "Skipping attachment %s: size %d exceeds limit %d",
                attachment.id, attachment.file_size, self._max_file_size,
            )
            attachment.download_status = DownloadStatus.SKIPPED
            attachment.download_error = (
                f"File size {attachment.file_size} exceeds limit {self._max_file_size}"
            )

        # Compute local path
        if not attachment.local_path:
            attachment.local_path = self._folder.resolve_path(attachment)

        self._store.append([attachment])
        return True

    def process_pending(self, batch_size: int = 10) -> list[dict[str, Any]]:
        """Process pending downloads. Returns results for each attempt."""
        if self._downloader is None:
            logger.warning("No downloader configured — cannot process pending attachments")
            return []

        pending = self._store.pending_downloads(limit=batch_size)
        results: list[dict[str, Any]] = []

        for att in pending:
            result = self._download_one(att)
            results.append(result)

        if results:
            logger.info(
                "Processed %d downloads: %d success, %d failed",
                len(results),
                sum(1 for r in results if r["success"]),
                sum(1 for r in results if not r["success"]),
            )
        return results

    def _download_one(self, attachment: Attachment) -> dict[str, Any]:
        """Download a single attachment."""
        if self._downloader is None:
            raise RuntimeError("No downloader configured")
        att_id = attachment.id

        # Resolve path if not set
        if not attachment.local_path:
            attachment.local_path = self._folder.resolve_path(attachment)

        # Mark as downloading
        self._store.update_status(att_id, DownloadStatus.DOWNLOADING)

        try:
            success = self._downloader.download(
                attachment.file_id, attachment.local_path
            )
            if success:
                self._store.update_status(
                    att_id,
                    DownloadStatus.COMPLETED,
                    local_path=attachment.local_path,
                    downloaded_at=time.time(),
                )
                logger.info("Downloaded attachment %s → %s", att_id, attachment.local_path)
                return {"id": att_id, "success": True, "path": attachment.local_path}
            else:
                self._store.update_status(
                    att_id,
                    DownloadStatus.FAILED,
                    error="Downloader returned False",
                )
                return {"id": att_id, "success": False, "error": "download returned False"}
        except Exception as e:
            logger.exception("Failed to download attachment %s", att_id)
            self._store.update_status(
                att_id,
                DownloadStatus.FAILED,
                error=str(e)[:500],
            )
            return {"id": att_id, "success": False, "error": str(e)[:200]}

    def retry_failed(self, batch_size: int = 10) -> list[dict[str, Any]]:
        """Retry previously failed downloads."""
        conn = self._store._conn
        rows = conn.execute(
            """UPDATE attachments SET download_status = 'pending'
               WHERE download_status = 'failed'
               AND id IN (
                   SELECT id FROM attachments
                   WHERE download_status = 'failed'
                   ORDER BY created_at ASC LIMIT ?
               )
               RETURNING id""",
            (batch_size,),
        ).fetchall()
        conn.commit()

        if rows:
            logger.info("Reset %d failed attachments to pending", len(rows))
            return self.process_pending(batch_size=batch_size)
        return []
