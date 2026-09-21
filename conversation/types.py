"""
Typed records for the Hive Conversation Store.

Core data model: Message (single utterance) and Thread (grouped messages).
All records are dataclasses with JSON-compatible serialization.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# ── helpers ──────────────────────────────────────────────

def _now() -> float:
    """UTC epoch seconds."""
    return time.time()


def _message_id(venue: str, venue_id: str, venue_message_id: str) -> str:
    """Deterministic message ID from venue coordinates."""
    raw = f"{venue}|{venue_id}|{venue_message_id}"
    return "msg_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── enums ────────────────────────────────────────────────

class VenueType:
    """Known venue types (not an enum for extensibility)."""
    TELEGRAM_GROUP = "telegram_group"
    TELEGRAM_DM = "telegram_dm"
    SLACK_CHANNEL = "slack_channel"
    TRANSCRIPT_FILE = "transcript_file"


class ContentType:
    """Message content types."""
    TEXT = "text"
    VOICE_TRANSCRIPT = "voice_transcript"
    MEDIA_CAPTION = "media_caption"
    SYSTEM = "system"  # join/leave/pin notifications


# ── records ──────────────────────────────────────────────

@dataclass
class Message:
    """A single utterance in a conversation.

    The primary unit of the Conversation Store. Each message has a
    deterministic ID derived from its venue coordinates, ensuring
    idempotent ingestion (dedup on append).
    """
    id: str = ""                          # Deterministic: venue + venue_id + venue_message_id
    venue: str = ""                       # VenueType value
    venue_id: str = ""                    # Chat/channel ID within the venue
    venue_message_id: str = ""            # Platform-native message ID
    thread_id: Optional[str] = None       # Thread/reply-chain ID if applicable
    sender_id: str = ""                   # Platform user ID
    sender_name: str = ""                 # Display name at time of message
    sender_agent_id: Optional[str] = None # Hive agent_id if sender is a known agent
    timestamp: float = field(default_factory=_now)  # UTC epoch seconds
    content: str = ""                     # Raw text content
    content_type: str = ContentType.TEXT   # ContentType value
    reply_to_id: Optional[str] = None     # ID of message this replies to
    metadata: dict[str, Any] = field(default_factory=dict)  # Platform-specific extras
    ingested_at: float = field(default_factory=_now)  # When the store received this
    schema_version: str = "1"

    def __post_init__(self):
        """Generate deterministic ID if not set."""
        if not self.id and self.venue and self.venue_id and self.venue_message_id:
            self.id = _message_id(self.venue, self.venue_id, self.venue_message_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        return cls(
            id=d.get("id", ""),
            venue=d.get("venue", ""),
            venue_id=d.get("venue_id", ""),
            venue_message_id=d.get("venue_message_id", ""),
            thread_id=d.get("thread_id"),
            sender_id=d.get("sender_id", ""),
            sender_name=d.get("sender_name", ""),
            sender_agent_id=d.get("sender_agent_id"),
            timestamp=d.get("timestamp", _now()),
            content=d.get("content", ""),
            content_type=d.get("content_type", ContentType.TEXT),
            reply_to_id=d.get("reply_to_id"),
            metadata=d.get("metadata", {}),
            ingested_at=d.get("ingested_at", _now()),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class Thread:
    """A group of related messages forming a conversational thread.

    Threads are assembled from Messages by the ThreadAssembler (P4).
    This type is defined here for forward compatibility.
    """
    id: str = ""                              # Deterministic from first message
    venue: str = ""
    venue_id: str = ""
    messages: list[Message] = field(default_factory=list)
    participant_ids: set[str] = field(default_factory=set)
    agent_participant_ids: set[str] = field(default_factory=set)
    started_at: float = 0.0
    last_activity: float = 0.0
    topic_summary: Optional[str] = None       # LLM-generated summary (lazy, P4)
    schema_version: str = "1"

    def add_message(self, msg: Message) -> None:
        """Add a message and update thread metadata."""
        self.messages.append(msg)
        self.participant_ids.add(msg.sender_id)
        if msg.sender_agent_id:
            self.agent_participant_ids.add(msg.sender_agent_id)
        if not self.started_at or msg.timestamp < self.started_at:
            self.started_at = msg.timestamp
        if msg.timestamp > self.last_activity:
            self.last_activity = msg.timestamp

    @property
    def message_count(self) -> int:
        return len(self.messages)
