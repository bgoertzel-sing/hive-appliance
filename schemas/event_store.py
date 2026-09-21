"""
SQLite-backed event store for the Omega Hive Appliance.

Provides append-only event persistence with typed queries.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from schemas.types import Event, EventKind, Severity

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    ts          REAL NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    subject     TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    severity    TEXT NOT NULL DEFAULT 'info',
    schema_version TEXT NOT NULL DEFAULT '1'
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_subject ON events(subject);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);

CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class EventStore:
    """Append-only SQLite event store."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self) -> None:
        if self.path == ":memory:":
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def append(self, event: Event) -> Event:
        """Append an event. Raises ValueError if id already exists."""
        d = event.to_dict()
        try:
            self._conn.execute(
                "INSERT INTO events (id, kind, ts, source, subject, payload, severity, schema_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (d["id"], d["kind"], d["ts"], d["source"], d["subject"],
                 json.dumps(d["payload"]), d["severity"], d["schema_version"]),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Event id {d['id']} already exists") from None
        return event

    def get(self, event_id: str) -> Optional[Event]:
        row = self._conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def query(
        self,
        *,
        kind: str | EventKind | None = None,
        source: str | None = None,
        subject: str | None = None,
        severity: str | Severity | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[Event]:
        sql = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind.value if isinstance(kind, EventKind) else kind)
        if source is not None:
            sql += " AND source = ?"
            params.append(source)
        if subject is not None:
            sql += " AND subject = ?"
            params.append(subject)
        if severity is not None:
            sql += " AND severity = ?"
            params.append(severity.value if isinstance(severity, Severity) else severity)
        if since is not None:
            sql += " AND ts >= ?"
            params.append(since)
        if until is not None:
            sql += " AND ts <= ?"
            params.append(until)
        sql += " ORDER BY ts ASC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def set_kv(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, value)
        )
        self._conn.commit()

    def get_kv(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return row["value"]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event.from_dict({
            "id": row["id"],
            "kind": row["kind"],
            "ts": row["ts"],
            "source": row["source"],
            "subject": row["subject"],
            "payload": json.loads(row["payload"]),
            "severity": row["severity"],
            "schema_version": row["schema_version"],
        })
