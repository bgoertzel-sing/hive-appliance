"""TranscriptFileCollector — ingest transcript.txt files into the Conversation Store.

Parses the line-based transcript format used by Iter agents:

    [2026-09-18 14:30:05] sender_name: message content here

Handles multi-line messages (continuation lines without a timestamp prefix)
and common edge cases (empty lines, system messages, unicode).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from conversation.types import Message, VenueType, ContentType


# ── line parser ──────────────────────────────────────────

# Matches: [2026-09-18 14:30:05] sender_name: content
_LINE_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+"  # timestamp
    r"(.+?):\s+"                                           # sender name
    r"(.*)$"                                               # content (may be empty)
)


def _parse_timestamp(ts_str: str) -> float:
    """Parse 'YYYY-MM-DD HH:MM:SS' to UTC epoch seconds."""
    import datetime
    dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


@dataclass
class _RawEntry:
    """A parsed transcript entry (possibly multi-line)."""
    timestamp: float
    sender_name: str
    content: str
    line_number: int


# ── collector ────────────────────────────────────────────

@dataclass
class TranscriptFileCollector:
    """Collects messages from an Iter-style transcript.txt file.

    Parameters
    ----------
    path:
        Absolute path to the transcript file.
    venue_id:
        Identifier for this transcript source (e.g. agent name or chat id).
        Defaults to the file's basename without extension.
    agent_map:
        Optional mapping of sender_name → agent_id for recognizing agents.
    """

    path: str
    venue_id: str = ""
    agent_map: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.venue_id:
            self.venue_id = os.path.splitext(os.path.basename(self.path))[0]

    # ── protocol properties ──────────────────────────────

    @property
    def venue_type(self) -> str:
        return VenueType.TRANSCRIPT_FILE

    # ── polling ──────────────────────────────────────────

    def poll(self, since_id: Optional[str] = None) -> list[Message]:
        """Parse transcript file and return messages.

        Parameters
        ----------
        since_id:
            If provided, only return messages whose venue_message_id
            (line number as string) is greater than this value.

        Returns
        -------
        list[Message]
            Messages in chronological order.
        """
        if not os.path.isfile(self.path):
            return []

        entries = self._parse_file()

        since_line = int(since_id) if since_id else 0
        messages = []
        for entry in entries:
            if entry.line_number <= since_line:
                continue
            msg = self._entry_to_message(entry)
            messages.append(msg)
        return messages

    # ── internal parsing ─────────────────────────────────

    def _parse_file(self) -> list[_RawEntry]:
        """Parse the transcript file into raw entries."""
        with open(self.path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        entries: list[_RawEntry] = []
        current: Optional[_RawEntry] = None

        for i, line in enumerate(lines, start=1):
            line_stripped = line.rstrip("\n\r")

            # Skip blank lines between entries
            if not line_stripped.strip():
                if current is not None:
                    current.content += "\n"
                continue

            m = _LINE_RE.match(line_stripped)
            if m:
                # Save previous entry
                if current is not None:
                    current.content = current.content.rstrip("\n")
                    entries.append(current)
                # Start new entry
                ts_str, sender, content = m.group(1), m.group(2), m.group(3)
                try:
                    ts = _parse_timestamp(ts_str)
                except ValueError:
                    ts = 0.0
                current = _RawEntry(
                    timestamp=ts,
                    sender_name=sender.strip(),
                    content=content,
                    line_number=i,
                )
            elif current is not None:
                # Continuation line
                current.content += "\n" + line_stripped
            # else: orphan line before first timestamped entry — skip

        # Don't forget the last entry
        if current is not None:
            current.content = current.content.rstrip("\n")
            entries.append(current)

        return entries

    def _entry_to_message(self, entry: _RawEntry) -> Message:
        """Convert a raw parsed entry into a Message."""
        sender_agent_id = self.agent_map.get(entry.sender_name)

        # Detect system messages
        content_type = ContentType.TEXT
        system_indicators = {"joined", "left", "pinned", "changed"}
        first_word = entry.content.split()[0].lower() if entry.content.strip() else ""
        if first_word in system_indicators and len(entry.content) < 100:
            content_type = ContentType.SYSTEM

        return Message(
            venue=self.venue_type,
            venue_id=self.venue_id,
            venue_message_id=str(entry.line_number),
            sender_id=entry.sender_name,
            sender_name=entry.sender_name,
            sender_agent_id=sender_agent_id,
            timestamp=entry.timestamp,
            content=entry.content,
            content_type=content_type,
        )

    # ── utility ──────────────────────────────────────────

    def count_entries(self) -> int:
        """Count parseable entries without building Message objects."""
        if not os.path.isfile(self.path):
            return 0
        return len(self._parse_file())
