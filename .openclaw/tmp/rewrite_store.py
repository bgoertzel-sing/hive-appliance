"""Rewrite store.py with all CS fixes applied to actual code structure."""

with open("conversation/store.py") as f:
    content = f.read()

# ── Fix 1: CS06/CS07 — Replace append method ──
old_append = '''    def append(self, messages: list[Message]) -> int:
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
        return added'''

new_append = '''    def append(self, messages: list[Message]) -> int:
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
                            content, content_type, reply_to_id, metadata,
                            ingested_at, schema_version)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            msg.id, msg.venue, msg.venue_id, msg.venue_message_id,
                            msg.thread_id, msg.sender_id, msg.sender_name,
                            msg.sender_agent_id, msg.timestamp, msg.content,
                            msg.content_type, msg.reply_to_id,
                            meta_json, msg.ingested_at,
                            msg.schema_version,
                        ),
                    )
                    added += 1
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
        return added'''

content = content.replace(old_append, new_append)

# ── Fix 2: Add get_by_id alias + context_around + recent methods ──
# Add after the existing get() method
old_get = '''    def get(self, message_id: str) -> Optional[Message]:
        """Fetch a single message by ID."""
        row = self._conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return self._row_to_message(row) if row else None'''

new_get = '''    def get(self, message_id: str) -> Optional[Message]:
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
        return [self._row_to_message(r) for r in rows]'''

content = content.replace(old_get, new_get)

# ── Fix 3: CS12 — Fix FTS search to push down venue_id filter and handle errors ──
old_search = '''    def search(self, query_text: str, k: int = 10, venue: Optional[str] = None) -> list[Message]:
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
        return [self._row_to_message(r) for r in rows]'''

new_search = '''    def search(
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
        return [self._row_to_message(r) for r in rows]'''

content = content.replace(old_search, new_search)

with open("conversation/store.py", "w") as f:
    f.write(content)

print("store.py fully updated: CS06/CS07/CS11/CS12 + get_by_id + context_around + recent")
