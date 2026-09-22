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

# ── validation constants ─────────────────────────────────

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",  # images
    "mp4", "webm", "mov", "avi", "mkv",                 # video
    "mp3", "ogg", "wav", "flac", "m4a", "opus",         # audio
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", # docs
    "txt", "csv", "json", "xml", "html", "md",          # text
    "zip", "tar", "gz", "7z", "rar",                    # archives
    "bin", "dat",                                        # binary
}

VALID_STATES = {
    "pending", "downloading", "completed", "failed", "cancelled",
}

# Lease timeout for crash recovery (AF07)
LEASE_TIMEOUT_SECONDS = 300  # 5 minutes
MAX_ATTEMPTS = 3

# ── defaults ─────────────────────────────────────────────

DEFAULT_DB_PATH = os.environ.get("HIVE_CONV_DB", "/hive/shared/conversation-store/messages.db")
DEFAULT_ATTACHMENTS_DIR = os.environ.get("HIVE_ATTACHMENTS_DIR", "/hive/shared/conversation-store/attachments")
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
        # AF11: validate extension
        ext = (attachment.extension or "bin").lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = "bin"
        filename = f"{attachment.id}.{ext}"

        with self._lock:
            dir_path.mkdir(parents=True, exist_ok=True)

        # AF04: verify resolved path is under base_dir
        full_path = (dir_path / filename).resolve()
        base_resolved = self._base_dir.resolve()
        if not str(full_path).startswith(str(base_resolved)):
            raise ValueError(f"Path escapes root: {full_path} not under {base_resolved}")
        # AF04: reject symlinks in path
        if dir_path.exists() and dir_path.is_symlink():
            raise ValueError(f"Symlink in path rejected: {dir_path}")
        return str(full_path)

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
                if self._conn.execute('SELECT changes()').fetchone()[0] > 0:
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
        """Update download status for an attachment.

        AF11: validates status is in VALID_STATES before writing.
        """
        if status not in VALID_STATES:
            raise ValueError(f"Invalid status {status!r}; must be one of {VALID_STATES}")
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

    def claim_pending(self, worker_id: str, limit: int = 10) -> list[Attachment]:
        """AF08: Exclusively claim pending downloads using CAS.

        Uses UPDATE ... WHERE to atomically claim rows. Only rows that
        are pending (or have expired leases) and under max attempts are claimed.
        """
        now = time.time()
        conn = self._conn
        rows = conn.execute(
            """SELECT id FROM attachments
               WHERE (download_status = 'pending'
                      OR (download_status = 'downloading'
                          AND lease_expires > 0
                          AND lease_expires < ?))
                 AND attempt_count < ?
               ORDER BY created_at ASC
               LIMIT ?""",
            (now, MAX_ATTEMPTS, limit),
        ).fetchall()

        claimed = []
        lease_until = now + LEASE_TIMEOUT_SECONDS
        for row in rows:
            aid = row["id"]
            conn.execute(
                """UPDATE attachments
                   SET download_status = 'downloading',
                       lease_owner = ?,
                       lease_expires = ?,
                       attempt_count = attempt_count + 1
                   WHERE id = ?
                     AND (download_status = 'pending'
                          OR (download_status = 'downloading'
                              AND lease_expires < ?))""",
                (worker_id, lease_until, aid, now),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                att = self.get(aid)
                if att:
                    claimed.append(att)
        conn.commit()
        return claimed

    def release_lease(self, attachment_id: str, worker_id: str) -> bool:
        """AF07: Release a lease (on graceful shutdown or success)."""
        conn = self._conn
        conn.execute(
            """UPDATE attachments
               SET lease_owner = '', lease_expires = 0
               WHERE id = ? AND lease_owner = ?""",
            (attachment_id, worker_id),
        )
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] > 0

    def recover_stale_leases(self) -> int:
        """AF07: Reset stale (crashed) downloads back to pending for retry."""
        now = time.time()
        conn = self._conn
        conn.execute(
            """UPDATE attachments
               SET download_status = 'pending',
                   lease_owner = '',
                   lease_expires = 0
               WHERE download_status = 'downloading'
                 AND lease_expires > 0
                 AND lease_expires < ?
                 AND attempt_count < ?""",
            (now, MAX_ATTEMPTS),
        )
        recovered = conn.execute("SELECT changes()").fetchone()[0]
        conn.execute(
            """UPDATE attachments
               SET download_status = 'failed',
                   download_error = 'max attempts exceeded',
                   lease_owner = '',
                   lease_expires = 0
               WHERE download_status = 'downloading'
                 AND lease_expires > 0
                 AND lease_expires < ?
                 AND attempt_count >= ?""",
            (now, MAX_ATTEMPTS),
        )
        conn.commit()
        return recovered

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


    # ── AF12: lifecycle ──────────────────────────────────

    def delete(self, attachment_id: str, remove_file: bool = True) -> bool:
        """Delete an attachment record and optionally its file."""
        att = self.get(attachment_id)
        if not att:
            return False
        if remove_file and att.local_path and os.path.isfile(att.local_path):
            try:
                os.remove(att.local_path)
            except OSError:
                logger.warning("Could not remove file %s", att.local_path)
        conn = self._conn
        conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        conn.commit()
        return True

    def delete_by_message(self, message_id: str, remove_files: bool = True) -> int:
        """Delete all attachments for a message."""
        atts = self.by_message(message_id)
        count = 0
        for att in atts:
            if self.delete(att.id, remove_file=remove_files):
                count += 1
        return count

    def apply_retention(self, max_age_seconds: float) -> int:
        """Delete attachments older than max_age_seconds."""
        cutoff = time.time() - max_age_seconds
        conn = self._conn
        rows = conn.execute(
            "SELECT id FROM attachments WHERE created_at < ?", (cutoff,)
        ).fetchall()
        count = 0
        for row in rows:
            if self.delete(row["id"]):
                count += 1
        return count

    def reconcile(self) -> dict:
        """AF12: Reconcile metadata vs filesystem.

        Returns counts of orphan_files, missing_files, repaired.
        """
        result = {"orphan_files": 0, "missing_files": 0, "repaired": 0}
        conn = self._conn
        rows = conn.execute(
            "SELECT id, local_path FROM attachments WHERE download_status = 'completed' AND local_path != ''"
        ).fetchall()
        for row in rows:
            if row["local_path"] and not os.path.isfile(row["local_path"]):
                result["missing_files"] += 1
                conn.execute(
                    "UPDATE attachments SET download_status = 'pending', local_path = '' WHERE id = ?",
                    (row["id"],),
                )
                result["repaired"] += 1
        conn.commit()
        return result

    def close(self) -> None:
        """Close the database connection."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None

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

        count = self._store.append([attachment])
        return count > 0  # AF10: accurate result — False if duplicate

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
        """Download a single attachment.

        AF05: Enforces actual byte-count limit (not just declared size).
        AF06: Uses atomic temp→rename publication.
        """
        if self._downloader is None:
            raise RuntimeError("No downloader configured")
        att_id = attachment.id

        # Resolve path if not set
        if not attachment.local_path:
            attachment.local_path = self._folder.resolve_path(attachment)

        final_path = attachment.local_path
        temp_path = final_path + ".part"

        # Mark as downloading
        self._store.update_status(att_id, DownloadStatus.DOWNLOADING)

        try:
            # AF06: Download to temp file first
            success = self._downloader.download(
                attachment.file_id, temp_path
            )
            if not success:
                # AF06: Clean up partial
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                self._store.update_status(
                    att_id,
                    DownloadStatus.FAILED,
                    error="Downloader returned False",
                )
                return {"id": att_id, "success": False, "error": "download returned False"}

            # AF06: Verify file actually exists after "success"
            if not os.path.isfile(temp_path):
                self._store.update_status(
                    att_id,
                    DownloadStatus.FAILED,
                    error="Downloader reported success but file does not exist",
                )
                return {"id": att_id, "success": False, "error": "file missing after download"}

            # AF05: Enforce actual byte-count limit
            actual_size = os.path.getsize(temp_path)
            if self._max_file_size > 0 and actual_size > self._max_file_size:
                os.remove(temp_path)
                err = f"Actual size {actual_size} exceeds limit {self._max_file_size}"
                self._store.update_status(att_id, DownloadStatus.FAILED, error=err)
                return {"id": att_id, "success": False, "error": err}

            # AF06: Atomic rename to final path
            shutil.move(temp_path, final_path)

            self._store.update_status(
                att_id,
                DownloadStatus.COMPLETED,
                local_path=final_path,
                downloaded_at=time.time(),
            )
            logger.info("Downloaded attachment %s -> %s (%d bytes)", att_id, final_path, actual_size)
            return {"id": att_id, "success": True, "path": final_path, "size": actual_size}
        except Exception as e:
            # AF06: Clean up partial on any error
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            logger.exception("Failed to download attachment %s", att_id)
            self._store.update_status(
                att_id,
                DownloadStatus.FAILED,
                error=str(e)[:500],
            )
            return {"id": att_id, "success": False, "error": str(e)[:200]}

    def retry_failed(self, batch_size: int = 10) -> list[dict[str, Any]]:
        """Retry previously failed downloads.

        AF10: Only retries the specific failed items, not unrelated pending work.
        """
        conn = self._store._conn
        rows = conn.execute(
            """SELECT id FROM attachments
               WHERE download_status = 'failed'
               ORDER BY created_at ASC LIMIT ?""",
            (batch_size,),
        ).fetchall()

        if not rows:
            return []

        retry_ids = [r["id"] for r in rows]
        logger.info("Retrying %d failed attachments", len(retry_ids))

        # Reset only these specific items
        for aid in retry_ids:
            conn.execute(
                "UPDATE attachments SET download_status = 'pending', download_error = '' WHERE id = ?",
                (aid,),
            )
        conn.commit()

        # Process only the items we just reset
        results = []
        for aid in retry_ids:
            att = self._store.get(aid)
            if att and att.download_status == DownloadStatus.PENDING:
                result = self._download_one(att)
                results.append(result)
        return results
