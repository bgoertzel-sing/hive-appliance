"""
MessageStore — append-only SQLite backend for the Conversation Store.

Provides durable, queryable storage with FTS5 full-text search.
WAL mode for concurrent read/write. Dedup on message ID.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from .types import Message

# ── defaults ─────────────────────────────────────────────

DEFAULT_DB_PATH = "/hive/shared/conversation-store/messages.db"


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

    # ── write ────────────────────────────────────────────

    def append(self, messages: list[Message]) -> int:
        """Append messages, dedup by ID. Returns count actually added."""
        if not messages:
            return 0
        conn = self._conn
        added = 0
        for msg in messages:
            try:
                conn.execute(
                    """INSERT INTO messages
                       (id, venue, venue_id, venue_message_id, thread_id,
                        sender_id, sender_name, sender_agent_id, timestamp,
                        content, content_type, reply_to_id, metadata,
                        ingested_at, schema_version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        msg.id, msg.venue, msg.venue_id, msg.venue_message_id,
                        msg.thread_id, msg.sender_id, msg.sender_name,
                        msg.sender_agent_id, msg.timestamp, msg.content,
                        msg.content_type, msg.reply_to_id,
                        json.dumps(msg.metadata), msg.ingested_at,
                        msg.schema_version,
                    ),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass  # Duplicate ID — skip silently (idempotent)
        conn.commit()
        return added

    # ── read ─────────────────────────────────────────────

    def get(self, message_id: str) -> Optional[Message]:
        """Fetch a single message by ID."""
        row = self._conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return self._row_to_message(row) if row else None

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

    def search(self, query_text: str, k: int = 10, venue: Optional[str] = None) -> list[Message]:
        """Full-text search via FTS5. Optional venue filter."""
        # FTS5 match with optional join filter
        if venue:
            sql = """
                SELECT m.* FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ? AND m.venue = ?
                ORDER BY rank LIMIT ?
            """
            rows = self._conn.execute(sql, (query_text, venue, k)).fetchall()
        else:
            sql = """
                SELECT m.* FROM messages m
                JOIN messages_fts fts ON m.rowid = fts.rowid
                WHERE messages_fts MATCH ?
                ORDER BY rank LIMIT ?
            """
            rows = self._conn.execute(sql, (query_text, k)).fetchall()
        return [self._row_to_message(r) for r in rows]

    def count(self, venue: Optional[str] = None) -> int:
        """Total message count, optionally filtered by venue."""
        if venue:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM messages WHERE venue = ?", (venue,)
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()
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
        return Message.from_dict(d)

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
