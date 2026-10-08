"""
MessageStore — append-only SQLite backend for the Conversation Store.

Provides durable, queryable storage with FTS5 full-text search.
WAL mode for concurrent read/write. Dedup on message ID.
"""
from __future__ import annotations

import logging

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .types import Message

# ── defaults ─────────────────────────────────────────────

DEFAULT_DB_PATH = "/hive/shared/conversation-store/messages.db"


logger = logging.getLogger(__name__)


class MessageStore:
    """Append-only, thread-safe SQLite message store with FTS5 search.

    Usage:
        store = MessageStore()          # uses default path
        store = MessageStore("/tmp/test.db")  # custom path
        n = store.append([msg1, msg2])  # deduped insert, returns count added
        msgs = store.query(venue="telegram_group", limit=50)
        msgs = store.search("hive appliance design", k=10)
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        # Initialize schema on the creating thread
        self._init_schema(self._conn)

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local connection (SQLite is not thread-safe by default)."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    # ── schema ───────────────────────────────────────────

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                venue           TEXT NOT NULL,
                venue_id        TEXT NOT NULL,
                venue_message_id TEXT NOT NULL,
                thread_id       TEXT,
                sender_id       TEXT NOT NULL,
                sender_name     TEXT NOT NULL DEFAULT '',
                sender_agent_id TEXT,
                timestamp       REAL NOT NULL,
                content         TEXT NOT NULL DEFAULT '',
                content_type    TEXT NOT NULL DEFAULT 'text',
                reply_to_id     TEXT,
                has_attachments INTEGER NOT NULL DEFAULT 0,
                attachment_ids  TEXT NOT NULL DEFAULT '[]',
                metadata        TEXT NOT NULL DEFAULT '{}',
                ingested_at     REAL NOT NULL,
                schema_version  TEXT NOT NULL DEFAULT '1'
            );

            CREATE INDEX IF NOT EXISTS idx_messages_venue
                ON messages(venue, venue_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_sender_agent
                ON messages(sender_agent_id)
                WHERE sender_agent_id IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_messages_thread
                ON messages(thread_id)
                WHERE thread_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS index_outbox (
                message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT ''
            );

            -- FTS5 full-text search on message content
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                id UNINDEXED,
                content,
                sender_name,
                content='messages',
                content_rowid='rowid'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, id, content, sender_name)
                VALUES (new.rowid, new.id, new.content, new.sender_name);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, id, content, sender_name)
                VALUES ('delete', old.rowid, old.id, old.content, old.sender_name);
            END;
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if "has_attachments" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN has_attachments INTEGER NOT NULL DEFAULT 0")
        if "attachment_ids" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN attachment_ids TEXT NOT NULL DEFAULT '[]'")
        conn.commit()

    # ── write ────────────────────────────────────────────

    def append(self, messages: list[Message]) -> int:
        """Append messages, dedup by ID. Returns count actually added.

        Validates each message before insertion (CS07). The entire batch
        uses explicit transaction management with rollback on failure (CS06).

        Raises
        ------
        ValueError
            If any message fails validation (non-finite timestamp,
            non-string content, unserializable metadata, empty ID, etc.).
        """
        if not messages:
            return 0

        # Phase 1: validate all messages and pre-serialize metadata BEFORE
        # touching the database (CS06: no open txn on failure,
        # CS07: reject invalid messages explicitly)
        validated: list[tuple[Message, str]] = []
        for msg in messages:
            errors = msg.validate()
            if errors:
                raise ValueError(
                    f"Invalid message (id={msg.id!r}): {'; '.join(errors)}"
                )
            meta_json = json.dumps(msg.metadata)
            validated.append((msg, meta_json))

        # Phase 2: insert within an explicit transaction with rollback safety
        conn = self._conn
        added = 0
        try:
            for msg, meta_json in validated:
                try:
                    conn.execute(
                        """INSERT INTO messages
                           (id, venue, venue_id, venue_message_id, thread_id,
                            sender_id, sender_name, sender_agent_id, timestamp,
                            content, content_type, reply_to_id, has_attachments,
                            attachment_ids, metadata, ingested_at, schema_version)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            msg.id, msg.venue, msg.venue_id, msg.venue_message_id,
                            msg.thread_id, msg.sender_id, msg.sender_name,
                            msg.sender_agent_id, msg.timestamp, msg.content,
                            msg.content_type, msg.reply_to_id,
                            int(msg.has_attachments), json.dumps(msg.attachment_ids),
                            meta_json, msg.ingested_at,
                            msg.schema_version,
                        ),
                    )
                    added += 1
                    conn.execute(
                        "INSERT OR IGNORE INTO index_outbox(message_id) VALUES (?)",
                        (msg.id,),
                    )
                except sqlite3.IntegrityError as exc:
                    # CS07: Only swallow UNIQUE constraint (duplicate ID).
                    # NOT NULL or CHECK violations are real errors.
                    err_msg = str(exc).lower()
                    if "unique" in err_msg or "primary" in err_msg:
                        pass  # duplicate ID — already stored
                    else:
                        raise
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                logger.debug("Rollback failed after store error", exc_info=True)
            raise
        return added

    def pending_index_messages(self, limit: int = 100) -> list[Message]:
        rows = self._conn.execute(
            """SELECT m.* FROM messages m JOIN index_outbox o ON o.message_id=m.id
               WHERE o.status='pending' ORDER BY m.ingested_at, m.id LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def mark_indexed(self, message_ids: list[str]) -> None:
        if not message_ids:
            return
        self._conn.executemany(
            "UPDATE index_outbox SET status='indexed', attempts=attempts+1, last_error='' WHERE message_id=?",
            [(message_id,) for message_id in message_ids],
        )
        self._conn.commit()

    def mark_index_failed(self, message_ids: list[str], error: str) -> None:
        self._conn.executemany(
            "UPDATE index_outbox SET attempts=attempts+1, last_error=? WHERE message_id=?",
            [(error[:500], message_id) for message_id in message_ids],
        )
        self._conn.commit()

    # ── read ─────────────────────────────────────────────

    def get(self, message_id: str) -> Optional[Message]:
        """Fetch a single message by ID."""
        row = self._conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return self._row_to_message(row) if row else None

    def get_by_native_id(self, venue: str, venue_id: str,
                         venue_message_id: str) -> Optional[Message]:
        row = self._conn.execute(
            "SELECT * FROM messages WHERE venue=? AND venue_id=? AND venue_message_id=?",
            (venue, venue_id, venue_message_id),
        ).fetchone()
        return self._row_to_message(row) if row else None

    # Alias for client.py compatibility
    get_by_id = get

    def context_around(
        self,
        message_id: str,
        before: int = 5,
        after: int = 5,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
    ) -> list[Message]:
        """Get messages surrounding a specific message.

        CS11: Returns up to *before* predecessors, the target itself, and up to
        *after* successors, ordered chronologically. Uses (timestamp, id) for
        stable ordering across ties. CS10: optional venue scope.
        """
        conn = self._conn
        target_row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        if target_row is None:
            return []
        target_ts = target_row["timestamp"]
        target_id = target_row["id"]

        # Build optional venue filter
        venue_clause = ""
        venue_params: list = []
        if venue:
            venue_clause += " AND venue = ?"
            venue_params.append(venue)
        if venue_id:
            venue_clause += " AND venue_id = ?"
            venue_params.append(venue_id)

        # Predecessors: DESC then reverse
        before_rows = conn.execute(
            f"""SELECT * FROM messages
               WHERE (timestamp < ? OR (timestamp = ? AND id < ?)){venue_clause}
               ORDER BY timestamp DESC, id DESC
               LIMIT ?""",
            [target_ts, target_ts, target_id] + venue_params + [before],
        ).fetchall()
        before_rows = list(reversed(before_rows))

        # Successors
        after_rows = conn.execute(
            f"""SELECT * FROM messages
               WHERE (timestamp > ? OR (timestamp = ? AND id > ?)){venue_clause}
               ORDER BY timestamp ASC, id ASC
               LIMIT ?""",
            [target_ts, target_ts, target_id] + venue_params + [after],
        ).fetchall()

        rows = before_rows + [target_row] + list(after_rows)
        return [self._row_to_message(r) for r in rows]

    def recent(
        self,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 50,
    ) -> list[Message]:
        """Get the most recent messages, optionally filtered.

        CS12: Returns the *limit* most recent matching records, presented
        in chronological order (oldest first).
        """
        if limit <= 0:
            return []
        conn = self._conn
        clauses: list[str] = []
        params: list = []
        if venue:
            clauses.append("venue = ?")
            params.append(venue)
        if venue_id:
            clauses.append("venue_id = ?")
            params.append(venue_id)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        # Fetch N most recent (DESC), then reverse to chronological
        rows = conn.execute(
            f"SELECT * FROM messages {where} ORDER BY timestamp DESC, id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        rows = list(reversed(rows))
        return [self._row_to_message(r) for r in rows]

    def query(
        self,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        sender_agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Structured query with optional filters."""
        clauses: list[str] = []
        params: list = []

        if venue is not None:
            clauses.append("venue = ?")
            params.append(venue)
        if venue_id is not None:
            clauses.append("venue_id = ?")
            params.append(venue_id)
        if sender_agent_id is not None:
            clauses.append("sender_agent_id = ?")
            params.append(sender_agent_id)
        if thread_id is not None:
            clauses.append("thread_id = ?")
            params.append(thread_id)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = " AND ".join(clauses) if clauses else "1"
        sql = f"SELECT * FROM messages WHERE {where} ORDER BY timestamp ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_message(r) for r in rows]

    def search(
        self,
        query_text: str,
        k: int = 10,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
    ) -> list[Message]:
        """Full-text search via FTS5 with pushed-down venue filters (CS12).

        Parameters
        ----------
        query_text:
            FTS5 match expression.
        k:
            Maximum results (applied after venue filtering).
        venue, venue_id:
            Optional filters pushed into SQL before LIMIT.
        """
        if k <= 0:
            return []
        # Build pushed-down venue filter
        extra_clauses = []
        params: list = [query_text]
        if venue:
            extra_clauses.append("m.venue = ?")
            params.append(venue)
        if venue_id:
            extra_clauses.append("m.venue_id = ?")
            params.append(venue_id)

        extra_where = (" AND " + " AND ".join(extra_clauses)) if extra_clauses else ""
        params.append(k)

        try:
            sql = f"""
                SELECT m.* FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?{extra_where}
                ORDER BY rank LIMIT ?
            """
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            # Catch FTS5 syntax errors from raw user input
            if "fts5" in str(exc).lower() or "syntax" in str(exc).lower():
                return []
            raise
        return [self._row_to_message(r) for r in rows]

    def count(
        self,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
    ) -> int:
        """Total message count, optionally filtered by venue/venue_id."""
        clauses: list[str] = []
        params: list = []
        if venue:
            clauses.append("venue = ?")
            params.append(venue)
        if venue_id:
            clauses.append("venue_id = ?")
            params.append(venue_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        row = self._conn.execute(
            f"SELECT COUNT(*) FROM messages {where}", params
        ).fetchone()
        return row[0] if row else 0

    def venues(self) -> list[dict]:
        """List all known venues with message counts."""
        rows = self._conn.execute(
            "SELECT venue, venue_id, COUNT(*) as cnt, MIN(timestamp) as first_ts, MAX(timestamp) as last_ts "
            "FROM messages GROUP BY venue, venue_id ORDER BY cnt DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── internals ────────────────────────────────────────

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        d["has_attachments"] = bool(d.get("has_attachments", 0))
        raw_ids = d.get("attachment_ids", "[]")
        d["attachment_ids"] = json.loads(raw_ids) if isinstance(raw_ids, str) else raw_ids
        return Message.from_dict(d)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        """Execute close operation."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
