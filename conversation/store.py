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
        # AF02: attachment columns
        for _col in [
            "ALTER TABLE messages ADD COLUMN has_attachments INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE messages ADD COLUMN attachment_ids TEXT NOT NULL DEFAULT '[]'",
        ]:
            try:
                conn.execute(_col)
            except sqlite3.OperationalError:
                pass
        # AF02/AF09: durable semantic outbox
        conn.execute("CREATE TABLE IF NOT EXISTS semantic_outbox (message_id TEXT PRIMARY KEY, content TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, indexed_at REAL)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outbox_pending ON semantic_outbox(indexed_at) WHERE indexed_at IS NULL")

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
            # AF09: reject cross-venue reply parents
            if msg.reply_to_id:
                # Ensure reply_to_id references same venue
                parent = self.get(msg.reply_to_id)
                if parent and parent.venue_id != msg.venue_id:
                    raise ValueError(
                        f'Cross-venue reply: msg {msg.id!r} (venue={msg.venue_id}) '
                        f'replies to {msg.reply_to_id!r} (venue={parent.venue_id})'
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
                            content, content_type, reply_to_id, metadata,
                            ingested_at, schema_version,
                            has_attachments, attachment_ids)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            msg.id, msg.venue, msg.venue_id, msg.venue_message_id,
                            msg.thread_id, msg.sender_id, msg.sender_name,
                            msg.sender_agent_id, msg.timestamp, msg.content,
                            msg.content_type, msg.reply_to_id,
                            meta_json, msg.ingested_at,
                            msg.schema_version,
                            1 if getattr(msg, "has_attachments", False) else 0,
                            __import__("json").dumps(getattr(msg, "attachment_ids", []) or []),
                        ),
                    )
                    added += 1
                    self._enqueue_semantic(conn, msg, meta_json)
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
                pass
            raise
        return added

    # ── read ─────────────────────────────────────────────

    def get(self, message_id: str) -> Optional[Message]:
        """Fetch a single message by ID."""
        row = self._conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
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


    # ── AF02: semantic outbox + reply resolver ────────────

    def _enqueue_semantic(self, conn, msg, meta_json):
        """Write message to semantic outbox for later indexing."""
        try:
            conn.execute(
                'INSERT OR IGNORE INTO semantic_outbox (message_id, content, metadata, created_at) VALUES (?, ?, ?, ?)',
                (msg.id, msg.content, meta_json, __import__('time').time()),
            )
        except Exception:
            pass

    def drain_semantic_outbox(self, semantic_index, batch_size=100):
        """AF02/AF09: Drain pending outbox entries to semantic index.

        Ensures SQL commits are eventually followed by semantic indexing.
        """
        conn = self._conn
        rows = conn.execute(
            'SELECT message_id, content, metadata FROM semantic_outbox WHERE indexed_at IS NULL ORDER BY created_at ASC LIMIT ?',
            (batch_size,),
        ).fetchall()
        if not rows:
            return 0
        indexed = 0
        for row in rows:
            try:
                meta = json.loads(row['metadata']) if row['metadata'] else {}
                semantic_index.index_single(row['message_id'], row['content'], meta)
                conn.execute(
                    'UPDATE semantic_outbox SET indexed_at = ? WHERE message_id = ?',
                    (__import__('time').time(), row['message_id']),
                )
                indexed += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning('Semantic index failed for %s: %s', row['message_id'], e)
        conn.commit()
        return indexed

    def resolve_reply(self, message_id):
        """AF02: Resolve the reply chain for a message using native coordinates."""
        chain = []
        seen = set()
        current_id = message_id
        while current_id and current_id not in seen:
            seen.add(current_id)
            msg = self.get(current_id)
            if not msg:
                break
            chain.append(msg)
            current_id = msg.reply_to_id
        return chain

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        # AF02: parse attachment fields from SQL
        if "has_attachments" in d:
            d["has_attachments"] = bool(d["has_attachments"])
        if "attachment_ids" in d and isinstance(d["attachment_ids"], str):
            d["attachment_ids"] = json.loads(d["attachment_ids"])
        return Message.from_dict(d)

    def close(self) -> None:
        """Execute close operation."""
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
