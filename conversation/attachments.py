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
import uuid
import inspect
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
VALID_DOWNLOAD_STATES = {"pending", "downloading", "completed", "failed", "skipped"}
TERMINAL_DOWNLOAD_STATES = {"completed", "failed", "skipped"}
_STATUS_SQL_LIST = ",".join(f"'{x}'" for x in sorted(VALID_DOWNLOAD_STATES))
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
        self._base_dir = Path(base_dir).resolve()
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
        filename = f"{self._component(attachment.id)}.{attachment.extension}"

        self._safe_mkdir(dir_path)

        return str(self._contained(dir_path / filename))

    def resolve_thumbnail_path(self, attachment: Attachment) -> str:
        """Compute thumbnail storage path."""
        dt = datetime.fromtimestamp(attachment.created_at, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        venue = self._sanitize(attachment.venue or "unknown")
        venue_id = self._sanitize(attachment.venue_id or "unknown")
        dir_path = self._base_dir / venue / venue_id / date_str / "thumbs"

        self._safe_mkdir(dir_path)

        return str(self._contained(dir_path / f"{self._component(attachment.id)}_thumb.jpg"))

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
                    pass  # Expected: file may vanish between walk and stat
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
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return safe[:100] or "unknown"  # Cap length

    @staticmethod
    def _component(name: str) -> str:
        if Path(name).name != name or name in {"", ".", ".."}:
            raise ValueError("unsafe attachment path component")
        return SharedFolderManager._sanitize(name)

    def _contained(self, path: Path) -> Path:
        resolved = path.resolve()
        if resolved != self._base_dir and self._base_dir not in resolved.parents:
            raise ValueError("attachment path escapes configured root")
        return resolved

    def _safe_mkdir(self, dir_path: Path) -> None:
        """P1: create dir_path under base_dir without ever following a symlink.

        Every component is validated *before* anything is created, so a
        planted symlink cannot cause directories to be made outside the root.
        """
        rel = dir_path.relative_to(self._base_dir)  # ValueError if not under root
        if any(part in ("", ".", "..") for part in rel.parts):
            raise ValueError("unsafe attachment directory component")
        with self._lock:
            if self._base_dir.is_symlink():
                raise ValueError("attachment root is a symlink")
            self._base_dir.mkdir(parents=True, exist_ok=True)
            cur = self._base_dir
            for part in rel.parts:
                cur = cur / part
                if cur.is_symlink():
                    raise ValueError(f"symlink in attachment path: {cur}")
                if cur.exists():
                    if not cur.is_dir():
                        raise ValueError(f"non-directory in attachment path: {cur}")
                else:
                    cur.mkdir()
                    if cur.is_symlink():  # raced in
                        raise ValueError(f"symlink in attachment path: {cur}")
            self._contained(dir_path)

    def attempt_artifact_path(self, canonical: str, attempt_id: str) -> Path:
        """A1: attempt-specific published file path (never shared by attempts)."""
        if not attempt_id or Path(attempt_id).name != attempt_id or attempt_id in {".", ".."}:
            raise ValueError("unsafe attempt id")
        base = Path(canonical)
        name = f"{base.stem}.{self._sanitize(attempt_id)}{base.suffix}"
        return self._contained(base.with_name(name))

    def is_safe_file(self, path: str) -> bool:
        """P2: path is a regular (non-symlink) file lexically and really inside root."""
        if not path:
            return False
        p = Path(path)
        if not p.is_absolute():
            return False
        try:
            p.relative_to(self._base_dir)
        except ValueError:
            return False
        if p.is_symlink():
            return False
        return self.contains(path)

    def contains(self, path: str) -> bool:
        try:
            self._contained(Path(path))
            return True
        except ValueError:
            return False


# ── attachment store ─────────────────────────────────────

class AttachmentStore:
    """SQLite-backed attachment metadata store.

    Uses the same database as MessageStore (shared SQLite file) with a
    separate 'attachments' table. Thread-safe via thread-local connections.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH,
                 attachments_root: Optional[str] = None):
        self._db_path = Path(db_path)
        # P2: files are only ever unlinked if contained in this root.
        self._root_folder = (SharedFolderManager(attachments_root)
                             if attachments_root else None)
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
                download_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (download_status IN ('completed','downloading','failed','pending','skipped')),
                download_error  TEXT NOT NULL DEFAULT '',
                thumbnail_path  TEXT NOT NULL DEFAULT '',
                duration        REAL,
                width           INTEGER,
                height          INTEGER,
                metadata        TEXT NOT NULL DEFAULT '{}',
                created_at      REAL NOT NULL,
                downloaded_at   REAL,
                schema_version  TEXT NOT NULL DEFAULT '1'
                ,attempt_id     TEXT NOT NULL DEFAULT ''
                ,lease_until    REAL
                ,actual_size    INTEGER NOT NULL DEFAULT 0
                ,retry_count    INTEGER NOT NULL DEFAULT 0
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
        columns = {row[1] for row in conn.execute("PRAGMA table_info(attachments)")}
        for name, definition in {
            "attempt_id": "TEXT NOT NULL DEFAULT ''",
            "lease_until": "REAL",
            "actual_size": "INTEGER NOT NULL DEFAULT 0",
            "retry_count": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE attachments ADD COLUMN {name} {definition}")
        # S1: legacy tables lack the CHECK constraint (SQLite cannot add one
        # via ALTER), so enforce the same invariant with triggers.
        for op in ("INSERT", "UPDATE"):
            conn.execute(f"""
                CREATE TRIGGER IF NOT EXISTS attachments_status_check_{op.lower()}
                BEFORE {op} ON attachments
                WHEN NEW.download_status NOT IN ({_STATUS_SQL_LIST})
                BEGIN SELECT RAISE(ABORT, 'invalid download_status'); END""")
        conn.commit()

    # ── write operations ─────────────────────────────────

    def append(self, attachments: list[Attachment]) -> int:
        """Insert attachments, deduplicating on ID. Returns count added."""
        if not attachments:
            return 0

        validated: list[tuple[Attachment, str]] = []
        for att in attachments:
            errors = att.validate()
            if errors:
                logger.warning("Rejected invalid attachment %s: %s", att.id, errors)
                return 0
            validated.append((att, json.dumps(att.metadata)))
        added = 0
        conn = self._conn
        try:
            for att, metadata_json in validated:
                has_messages = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'"
                ).fetchone()
                if has_messages:
                    parent = conn.execute(
                        "SELECT venue, venue_id FROM messages WHERE id=?", (att.message_id,)
                    ).fetchone()
                    if parent is None:
                        raise ValueError(f"attachment parent {att.message_id!r} does not exist")
                    if parent["venue"] != att.venue or parent["venue_id"] != att.venue_id:
                        raise ValueError("attachment venue does not match its parent message")
                cursor = conn.execute(
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
                        metadata_json, att.created_at,
                        att.downloaded_at, att.schema_version,
                    ),
                )
                added += cursor.rowcount
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
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
        if status not in VALID_DOWNLOAD_STATES:
            raise ValueError(f"Invalid download status {status!r}; expected one of {VALID_DOWNLOAD_STATES}")
        conn = self._conn
        try:
            cursor = conn.execute(
                """UPDATE attachments
                   SET download_status = ?, local_path = ?,
                       download_error = ?, downloaded_at = ?
                   WHERE id = ?""",
                (status, local_path, error, downloaded_at, attachment_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except sqlite3.Error:
            logger.exception("Error updating attachment status %s", attachment_id)
            return False

    def claim_pending(self, limit: int, lease_seconds: float = 300.0) -> list[Attachment]:
        now = time.time()
        conn = self._conn
        claimed: list[Attachment] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """UPDATE attachments SET download_status='pending', attempt_id='',
                   lease_until=NULL, retry_count=retry_count+1
                   WHERE download_status='downloading' AND lease_until < ?""", (now,)
            )
            ids = [row[0] for row in conn.execute(
                """SELECT id FROM attachments WHERE download_status='pending'
                   ORDER BY created_at, id LIMIT ?""", (limit,)
            ).fetchall()]
            for attachment_id in ids:
                attempt_id = uuid.uuid4().hex
                cursor = conn.execute(
                    """UPDATE attachments SET download_status='downloading',
                       attempt_id=?, lease_until=? WHERE id=? AND download_status='pending'""",
                    (attempt_id, now + lease_seconds, attachment_id),
                )
                if cursor.rowcount:
                    row = conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
                    claimed.append(self._row_to_attachment(row))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        return claimed

    def finish_attempt(self, attachment_id: str, attempt_id: str, status: str,
                       local_path: str = "", error: str = "",
                       actual_size: int = 0) -> bool:
        # S1: an attempt can only finish into a terminal state.
        if status not in TERMINAL_DOWNLOAD_STATES:
            raise ValueError(f"Invalid terminal status {status!r}; expected one of "
                             f"{sorted(TERMINAL_DOWNLOAD_STATES)}")
        if not attempt_id:
            raise ValueError("finish_attempt requires an attempt_id")
        cursor = self._conn.execute(
            """UPDATE attachments SET download_status=?, local_path=?, download_error=?,
               downloaded_at=?, actual_size=?, lease_until=NULL
               WHERE id=? AND attempt_id=? AND download_status='downloading'""",
            (status, local_path, error,
             time.time() if status == DownloadStatus.COMPLETED else None,
             actual_size, attachment_id, attempt_id),
        )
        self._conn.commit()
        return cursor.rowcount == 1

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
            "SELECT COALESCE(SUM(actual_size), 0) FROM attachments WHERE download_status = 'completed'"
        ).fetchone()
        downloaded_bytes = row[0] if row else 0
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "downloading": self.count(DownloadStatus.DOWNLOADING),
            "skipped": self.count(DownloadStatus.SKIPPED),
            "downloaded_bytes": downloaded_bytes,
            "downloaded_mb": round(downloaded_bytes / (1024 * 1024), 2),
        }

    def delete(self, attachment_id: str, remove_file: bool = True,
               folder: Optional["SharedFolderManager"] = None) -> bool:
        """Delete an attachment row and (optionally) its file.

        P2: the file is removed only if it is a regular file contained in the
        configured attachments root (folder or attachments_root).  Paths
        outside the root, symlinks, or an unknown root are never unlinked;
        the metadata row is still deleted.
        """
        attachment = self.get(attachment_id)
        if attachment is None:
            return False
        root = folder or self._root_folder
        if remove_file and attachment.local_path:
            if root is None or not root.is_safe_file(attachment.local_path):
                logger.warning("Refusing to unlink uncontained attachment file %s",
                               attachment.local_path)
            else:
                try:
                    Path(attachment.local_path).unlink(missing_ok=True)
                except OSError:
                    logger.exception("Unable to remove attachment file %s", attachment.local_path)
        cursor = self._conn.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))
        self._conn.commit()
        return cursor.rowcount == 1

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

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
            attempt_id=row["attempt_id"],
            lease_until=row["lease_until"],
            actual_size=row["actual_size"],
            retry_count=row["retry_count"],
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
        self._downloaders: dict[tuple[str, str], AttachmentDownloader] = {}
        self._max_file_size = max_file_size
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def set_downloader(self, downloader: AttachmentDownloader) -> None:
        """Set or replace the platform downloader."""
        self._downloader = downloader

    def register_downloader(self, venue: str, downloader: AttachmentDownloader,
                            account_id: str = "default") -> None:
        self._downloaders[(venue, account_id)] = downloader

    def _downloader_for(self, attachment: Attachment) -> Optional[AttachmentDownloader]:
        account_id = str(attachment.metadata.get("telegram_account_id")
                         or attachment.metadata.get("account_id") or "default")
        return self._downloaders.get((attachment.venue, account_id), self._downloader)

    @property
    def store(self) -> AttachmentStore:
        return self._store

    @property
    def folder(self) -> SharedFolderManager:
        return self._folder

    def enqueue(self, attachment: Attachment) -> bool:
        """Register an attachment for download.

        Returns True if successfully enqueued (or already exists).
        """
        errors = attachment.validate()
        if errors:
            return False
        if attachment.local_path and not self._folder.contains(attachment.local_path):
            return False
        downloader = self._downloader_for(attachment)
        if downloader is not None:
            try:
                info = downloader.get_file_info(attachment.file_id)
                remote_size = int(info.get("size", info.get("file_size", 0)) or 0)
                if remote_size:
                    attachment.file_size = remote_size
            except (AttributeError, NotImplementedError):
                pass  # Expected: downloader may not support get_file_info
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

        return self._store.append([attachment]) == 1

    def process_pending(self, batch_size: int = 10) -> list[dict[str, Any]]:
        """Process pending downloads. Returns results for each attempt."""
        if self._downloader is None and not self._downloaders:
            logger.warning("No downloader configured — cannot process pending attachments")
            return []

        pending = self._store.claim_pending(limit=batch_size)
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
        downloader = self._downloader_for(attachment)
        if downloader is None:
            raise RuntimeError("No downloader configured")
        att_id = attachment.id

        # P2/A1: never trust a stored local_path; always derive a contained,
        # attempt-specific artifact path so a losing attempt can only ever
        # touch its own files.
        try:
            canonical = self._folder.resolve_path(attachment)
            final_path = self._folder.attempt_artifact_path(canonical, attachment.attempt_id)
        except ValueError as e:
            self._store.finish_attempt(att_id, attachment.attempt_id,
                                       DownloadStatus.FAILED, error=str(e)[:500])
            return {"id": att_id, "success": False, "error": str(e)[:200]}
        attachment.local_path = str(final_path)
        temp_path = final_path.with_name(f".{final_path.name}.{attachment.attempt_id}.part")

        try:
            parameters = inspect.signature(downloader.download).parameters
            if "max_bytes" in parameters:
                success = downloader.download(
                    attachment.file_id, str(temp_path), max_bytes=self._max_file_size
                )
            else:
                success = downloader.download(attachment.file_id, str(temp_path))
            if success:
                if not temp_path.is_file():
                    raise RuntimeError("downloader reported success without producing a file")
                actual_size = temp_path.stat().st_size
                if self._max_file_size > 0 and actual_size > self._max_file_size:
                    raise ValueError(
                        f"downloaded size {actual_size} exceeds limit {self._max_file_size}"
                    )
                if not (self._folder.contains(str(final_path))
                        and not final_path.parent.is_symlink()):
                    raise ValueError("publish path escapes attachment root")
                os.replace(temp_path, final_path)
                if not self._store.finish_attempt(
                    att_id, attachment.attempt_id, DownloadStatus.COMPLETED,
                    local_path=str(final_path), actual_size=actual_size,
                ):
                    # A1: only this attempt's own artifact is removed.
                    final_path.unlink(missing_ok=True)
                    raise RuntimeError("download lease was lost before publication")
                logger.info("Downloaded attachment %s → %s", att_id, attachment.local_path)
                return {"id": att_id, "success": True, "path": attachment.local_path}
            else:
                temp_path.unlink(missing_ok=True)
                self._store.finish_attempt(att_id, attachment.attempt_id,
                                           DownloadStatus.FAILED,
                                           error="Downloader returned False")
                return {"id": att_id, "success": False, "error": "download returned False"}
        except Exception as e:
            logger.exception("Failed to download attachment %s", att_id)
            temp_path.unlink(missing_ok=True)
            self._store.finish_attempt(att_id, attachment.attempt_id,
                                       DownloadStatus.FAILED,
                                       error=str(e)[:500])
            return {"id": att_id, "success": False, "error": str(e)[:200]}

    def retry_failed(self, batch_size: int = 10) -> list[dict[str, Any]]:
        """Retry previously failed downloads."""
        conn = self._store._conn
        rows = conn.execute(
            """UPDATE attachments SET download_status = 'pending', download_error=''
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
            ids = {row[0] for row in rows}
            claimed = self._store.claim_pending(limit=max(self._store.count(), batch_size))
            results = []
            for attachment in claimed:
                if attachment.id in ids:
                    results.append(self._download_one(attachment))
                else:
                    self._store.finish_attempt(
                        attachment.id, attachment.attempt_id,
                        DownloadStatus.PENDING, local_path=attachment.local_path
                    )
            return results
        return []

    def reconcile(self) -> dict[str, int]:
        repaired = {"missing_completed": 0, "recovered_downloading": 0,
                    "orphan_partials": 0}
        conn = self._store._conn
        now = time.time()
        cursor = conn.execute(
            """UPDATE attachments SET download_status='pending', attempt_id='',
               lease_until=NULL WHERE download_status='downloading'
               AND (lease_until IS NULL OR lease_until < ?)""", (now,)
        )
        repaired["recovered_downloading"] = cursor.rowcount
        rows = conn.execute(
            "SELECT id, local_path FROM attachments WHERE download_status='completed'"
        ).fetchall()
        for row in rows:
            if not row["local_path"] or not Path(row["local_path"]).is_file():
                conn.execute(
                    """UPDATE attachments SET download_status='failed',
                       download_error='completed file is missing' WHERE id=?""",
                    (row["id"],),
                )
                repaired["missing_completed"] += 1
        conn.commit()
        # A2: partials belonging to a live lease are in-flight, not orphans.
        active = {row[0] for row in conn.execute(
            """SELECT attempt_id FROM attachments WHERE download_status='downloading'
               AND attempt_id != '' AND lease_until IS NOT NULL AND lease_until >= ?""",
            (now,),
        ).fetchall()}
        repaired["active_partials_kept"] = 0
        base = self._folder.base_dir
        if base.exists() and not base.is_symlink():
            for dirpath, _dirs, files in os.walk(base, followlinks=False):
                for fname in files:
                    if not (fname.startswith(".") and fname.endswith(".part")):
                        continue
                    partial = Path(dirpath) / fname
                    attempt = fname[:-len(".part")].rsplit(".", 1)[-1]
                    if attempt in active:
                        repaired["active_partials_kept"] += 1
                        continue
                    if partial.is_symlink() or not self._folder.contains(str(partial)):
                        continue
                    try:
                        partial.unlink()
                        repaired["orphan_partials"] += 1
                    except OSError:
                        logger.exception("Unable to remove orphan partial %s", partial)
        return repaired

    def start(self, poll_interval: float = 1.0, batch_size: int = 10) -> None:
        if self._worker is not None:
            if self._worker.is_alive():
                if self._stop_event.is_set():
                    # L1: a previous stop() timed out; the old worker may
                    # still be mid-download.  Never run two workers.
                    raise RuntimeError(
                        "previous attachment worker has not exited; refusing restart")
                return
            self._worker = None
        self._stop_event.clear()

        def work() -> None:
            self.reconcile()
            while not self._stop_event.is_set():
                self.process_pending(batch_size)
                self._stop_event.wait(poll_interval)

        self._worker = threading.Thread(
            target=work, name="attachment-download-worker", daemon=True
        )
        self._worker.start()

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop the worker. Returns True if it exited.

        L1: if the worker does not exit within timeout, the reference is
        kept (so start() can refuse a concurrent restart) and False is
        returned.
        """
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout)
            if self._worker.is_alive():
                logger.warning("Attachment worker did not stop within %.1fs", timeout)
                return False
            self._worker = None
        return True
