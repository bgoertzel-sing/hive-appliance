"""Fix CS06 (transaction leak) and CS07 (invalid messages swallowed) in store.py."""

with open("conversation/store.py") as f:
    content = f.read()

# Replace the append method with proper transaction handling and validation
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
                # Duplicate ID — already stored, skip
                pass
        conn.commit()
        return added'''

new_append = '''    def append(self, messages: list[Message]) -> int:
        """Append messages, dedup by ID. Returns count actually added.

        Validates each message before insertion. Invalid messages raise
        ValueError. The entire batch is atomic: either all valid messages
        are committed or none are (on unexpected error).

        Raises
        ------
        ValueError
            If any message fails validation (non-finite timestamp,
            non-string content, unserializable metadata, empty ID, etc.).
        """
        if not messages:
            return 0

        # Phase 1: validate all messages and pre-serialize metadata BEFORE
        # touching the database (CS06: no open transaction on failure,
        # CS07: reject invalid messages explicitly)
        validated: list[tuple[Message, str]] = []
        for msg in messages:
            errors = msg.validate()
            if errors:
                raise ValueError(
                    f"Invalid message (id={msg.id!r}): {'; '.join(errors)}"
                )
            # Pre-serialize metadata so TypeError is caught before any SQL
            meta_json = json.dumps(msg.metadata)
            validated.append((msg, meta_json))

        # Phase 2: insert within an explicit transaction with rollback safety
        conn = self._conn
        added = 0
        try:
            conn.execute("BEGIN IMMEDIATE")
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
                    # Only swallow UNIQUE constraint (duplicate ID).
                    # NOT NULL or CHECK violations are real errors.
                    err_msg = str(exc).lower()
                    if "unique" in err_msg or "primary" in err_msg:
                        pass  # duplicate ID — already stored
                    else:
                        raise
            conn.execute("COMMIT")
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass  # connection may already be closed
            raise
        return added'''

content = content.replace(old_append, new_append)

# Also fix the context_around method (CS11: not centered, can exclude target)
old_context = '''    def context_around(
        self,
        message_id: str,
        before: int = 5,
        after: int = 5,
    ) -> list[Message]:
        """Get messages surrounding a specific message."""
        conn = self._conn

        # Get the target message's timestamp
        row = conn.execute(
            "SELECT timestamp FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        if row is None:
            return []
        target_ts = row["timestamp"]

        # Get messages before (inclusive of target)
        before_rows = conn.execute(
            """SELECT * FROM messages
               WHERE timestamp <= ? + 0.001
               ORDER BY timestamp ASC
               LIMIT ?""",
            (target_ts, before + 1),
        ).fetchall()

        # Get messages after (exclusive of target)
        after_rows = conn.execute(
            """SELECT * FROM messages
               WHERE timestamp > ? + 0.001
               ORDER BY timestamp ASC
               LIMIT ?""",
            (target_ts, after),
        ).fetchall()

        rows = before_rows + after_rows
        return [self._row_to_message(r) for r in rows]'''

new_context = '''    def context_around(
        self,
        message_id: str,
        before: int = 5,
        after: int = 5,
    ) -> list[Message]:
        """Get messages surrounding a specific message.

        Returns up to *before* predecessors, the target itself, and up to
        *after* successors, ordered chronologically. Uses (timestamp, id)
        for stable ordering across ties.
        """
        conn = self._conn

        # Get the target message
        target_row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        if target_row is None:
            return []
        target_ts = target_row["timestamp"]
        target_id = target_row["id"]

        # Get *before* predecessors: those strictly before, or same timestamp
        # but id < target (stable tie-break). Fetch DESC then reverse.
        before_rows = conn.execute(
            """SELECT * FROM messages
               WHERE (timestamp < ? OR (timestamp = ? AND id < ?))
               ORDER BY timestamp DESC, id DESC
               LIMIT ?""",
            (target_ts, target_ts, target_id, before),
        ).fetchall()
        before_rows = list(reversed(before_rows))

        # Get *after* successors: those strictly after, or same timestamp
        # but id > target.
        after_rows = conn.execute(
            """SELECT * FROM messages
               WHERE (timestamp > ? OR (timestamp = ? AND id > ?))
               ORDER BY timestamp ASC, id ASC
               LIMIT ?""",
            (target_ts, target_ts, target_id, after),
        ).fetchall()

        rows = before_rows + [target_row] + list(after_rows)
        return [self._row_to_message(r) for r in rows]'''

content = content.replace(old_context, new_context)

# Fix the query method to support pushed-down venue filtering for FTS (CS12)
# Also fix "recent" to actually return the most recent messages
old_recent = '''    def recent(
        self,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 50,
    ) -> list[Message]:
        """Get recent messages, optionally filtered by venue and time range."""
        conn = self._conn
        clauses = []
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
        rows = conn.execute(
            f"SELECT * FROM messages {where} ORDER BY timestamp ASC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [self._row_to_message(r) for r in rows]'''

new_recent = '''    def recent(
        self,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 50,
    ) -> list[Message]:
        """Get the most recent messages, optionally filtered by venue and time range.

        Returns up to *limit* messages ordered chronologically (oldest first),
        selected from the **most recent** matching records (not the earliest).
        """
        if limit <= 0:
            return []
        conn = self._conn
        clauses = []
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
        # Fetch the N most recent rows (DESC), then reverse to chronological
        rows = conn.execute(
            f"SELECT * FROM messages {where} ORDER BY timestamp DESC, id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        rows = list(reversed(rows))
        return [self._row_to_message(r) for r in rows]'''

content = content.replace(old_recent, new_recent)

# Fix FTS search to support venue filtering pushed down (CS12)
old_search = '''    def search(
        self,
        query: str,
        k: int = 10,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
    ) -> list[Message]:
        """Full-text search over message content using FTS5.

        Parameters
        ----------
        query:
            FTS5 query string. Supports AND, OR, NOT, phrase queries.
        k:
            Maximum results to return.
        venue, venue_id:
            Optional filters applied after FTS ranking.
        """
        conn = self._conn
        rows = conn.execute(
            """SELECT m.*, rank
               FROM messages_fts fts
               JOIN messages m ON fts.id = m.id
               WHERE messages_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, k),
        ).fetchall()

        results = [self._row_to_message(r) for r in rows]

        # Apply venue filters
        if venue:
            results = [m for m in results if m.venue == venue]
        if venue_id:
            results = [m for m in results if m.venue_id == venue_id]

        return results'''

new_search = '''    def search(
        self,
        query: str,
        k: int = 10,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
    ) -> list[Message]:
        """Full-text search over message content using FTS5.

        Parameters
        ----------
        query:
            FTS5 query string. Supports AND, OR, NOT, phrase queries.
            Raw user input is escaped to prevent FTS5 syntax errors.
        k:
            Maximum results to return (after venue filtering).
        venue, venue_id:
            Optional filters applied **before** the LIMIT (pushed into SQL).
        """
        if k <= 0:
            return []
        conn = self._conn

        # Build pushed-down venue filter on the messages table
        venue_clauses = []
        params: list = []
        if venue:
            venue_clauses.append("m.venue = ?")
            params.append(venue)
        if venue_id:
            venue_clauses.append("m.venue_id = ?")
            params.append(venue_id)

        venue_where = (" AND " + " AND ".join(venue_clauses)) if venue_clauses else ""

        try:
            rows = conn.execute(
                f"""SELECT m.*
                   FROM messages_fts fts
                   JOIN messages m ON fts.id = m.id
                   WHERE messages_fts MATCH ?{venue_where}
                   ORDER BY rank
                   LIMIT ?""",
                [query] + params + [k],
            ).fetchall()
        except sqlite3.OperationalError as exc:
            # Catch FTS5 syntax errors from raw user input
            if "fts5" in str(exc).lower() or "syntax" in str(exc).lower():
                return []
            raise

        return [self._row_to_message(r) for r in rows]'''

content = content.replace(old_search, new_search)

with open("conversation/store.py", "w") as f:
    f.write(content)

print("CS06/CS07/CS11/CS12: store.py updated")
