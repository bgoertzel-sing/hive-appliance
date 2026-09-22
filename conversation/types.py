"""
Typed records for the Hive Conversation Store.

Core data model: Message (single utterance), Thread (grouped messages),
and Attachment (media/file associated with a message).
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
    """Deterministic message ID from venue coordinates.

    Uses length-prefixed encoding to prevent delimiter collisions:
    e.g. ('a|b', 'c') vs ('a', 'b|c') produce different hashes.
    """
    parts = [venue, venue_id, venue_message_id]
    raw = ":".join(f"{len(p)}:{p}" for p in parts)
    return "msg_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _attachment_id(message_id: str, file_id: str) -> str:
    """Deterministic attachment ID from message + platform file identifier."""
    parts = [message_id, file_id]
    raw = ":".join(f"{len(p)}:{p}" for p in parts)
    return "att_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


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
    ATTACHMENT = "attachment"  # Message is primarily an attachment
    SYSTEM = "system"  # join/leave/pin notifications


class AttachmentType:
    """Attachment media types."""
    PHOTO = "photo"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    VOICE = "voice"
    VIDEO_NOTE = "video_note"
    STICKER = "sticker"
    ANIMATION = "animation"  # GIF
    UNKNOWN = "unknown"


class DownloadStatus:
    """Attachment download status."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # Too large, unsupported, etc.


# ── records ──────────────────────────────────────────────

@dataclass
class Attachment:
    """A file/media attachment associated with a message.

    Each attachment has a deterministic ID derived from its parent message
    and the platform-specific file identifier, ensuring idempotent storage.
    """
    id: str = ""                          # Deterministic: message_id + file_id
    message_id: str = ""                  # Parent message ID
    venue: str = ""                       # VenueType (copied from message)
    venue_id: str = ""                    # Chat/channel ID (copied from message)
    attachment_type: str = AttachmentType.UNKNOWN
    file_id: str = ""                     # Platform-native file identifier
    file_unique_id: str = ""              # Platform-native unique file ID (Telegram)
    file_name: str = ""                   # Original filename if available
    file_size: int = 0                    # Size in bytes (0 = unknown)
    mime_type: str = ""                   # MIME type if known
    local_path: str = ""                  # Path in shared folder after download
    download_status: str = DownloadStatus.PENDING
    download_error: str = ""              # Error message if download failed
    thumbnail_path: str = ""              # Path to thumbnail if available
    duration: Optional[float] = None      # Duration in seconds for audio/video
    width: Optional[int] = None           # Width in pixels for images/video
    height: Optional[int] = None          # Height in pixels for images/video
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=_now)
    downloaded_at: Optional[float] = None
    schema_version: str = "1"

    def __post_init__(self):
        """Generate deterministic ID if not set."""
        if not self.id and self.message_id and self.file_id:
            self.id = _attachment_id(self.message_id, self.file_id)

    def validate(self) -> list[str]:
        """Validate attachment fields."""
        errors: list[str] = []
        if not self.id:
            errors.append("id is empty or unset")
        if not self.message_id:
            errors.append("message_id is empty")
        if not self.file_id:
            errors.append("file_id is empty")
        if self.file_size < 0:
            errors.append(f"file_size is negative: {self.file_size}")
        return errors

    @property
    def is_downloaded(self) -> bool:
        """Return is downloaded."""
        return self.download_status == DownloadStatus.COMPLETED

    @property
    def extension(self) -> str:
        """Infer file extension from filename or mime_type."""
        if self.file_name and "." in self.file_name:
            return self.file_name.rsplit(".", 1)[-1].lower()
        mime_ext = {
            "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
            "image/webp": "webp", "audio/ogg": "ogg", "audio/mpeg": "mp3",
            "video/mp4": "mp4", "application/pdf": "pdf",
            "text/plain": "txt", "application/zip": "zip",
        }
        return mime_ext.get(self.mime_type, "bin")

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Attachment:
        """Execute from dict operation."""
        return cls(
            id=d.get("id", ""),
            message_id=d.get("message_id", ""),
            venue=d.get("venue", ""),
            venue_id=d.get("venue_id", ""),
            attachment_type=d.get("attachment_type", AttachmentType.UNKNOWN),
            file_id=d.get("file_id", ""),
            file_unique_id=d.get("file_unique_id", ""),
            file_name=d.get("file_name", ""),
            file_size=d.get("file_size", 0),
            mime_type=d.get("mime_type", ""),
            local_path=d.get("local_path", ""),
            download_status=d.get("download_status", DownloadStatus.PENDING),
            download_error=d.get("download_error", ""),
            thumbnail_path=d.get("thumbnail_path", ""),
            duration=d.get("duration"),
            width=d.get("width"),
            height=d.get("height"),
            metadata=d.get("metadata", {}),
            created_at=d.get("created_at", _now()),
            downloaded_at=d.get("downloaded_at"),
            schema_version=d.get("schema_version", "1"),
        )


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
    has_attachments: bool = False          # Whether message has file attachments
    attachment_ids: list[str] = field(default_factory=list)  # Attachment IDs
    metadata: dict[str, Any] = field(default_factory=dict)  # Platform-specific extras
    ingested_at: float = field(default_factory=_now)  # When the store received this
    schema_version: str = "1"

    def __post_init__(self):
        """Generate deterministic ID if not set."""
        if not self.id and self.venue and self.venue_id and self.venue_message_id:
            self.id = _message_id(self.venue, self.venue_id, self.venue_message_id)

    def validate(self) -> list[str]:
        """Validate message fields. Returns list of error strings (empty = valid).

        Checks: non-empty ID, non-empty venue coordinates, finite timestamp,
        content is a string, metadata is serializable.
        """
        import math
        errors: list[str] = []
        if not self.id:
            errors.append("id is empty or unset")
        if not self.venue:
            errors.append("venue is empty")
        if not self.venue_id:
            errors.append("venue_id is empty")
        if not self.venue_message_id:
            errors.append("venue_message_id is empty")
        if not isinstance(self.timestamp, (int, float)):
            errors.append(f"timestamp is not numeric: {type(self.timestamp).__name__}")
        elif math.isnan(self.timestamp) or math.isinf(self.timestamp):
            errors.append(f"timestamp is not finite: {self.timestamp}")
        if not isinstance(self.content, str):
            errors.append(f"content is not a string: {type(self.content).__name__}")
        if not isinstance(self.sender_id, str):
            errors.append(f"sender_id is not a string: {type(self.sender_id).__name__}")
        # Validate metadata is JSON-serializable
        try:
            import json
            json.dumps(self.metadata)
        except (TypeError, ValueError) as e:
            errors.append(f"metadata is not JSON-serializable: {e}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        """Execute from dict operation."""
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
            has_attachments=d.get("has_attachments", False),
            attachment_ids=d.get("attachment_ids", []),
            metadata=d.get("metadata", {}),
            ingested_at=d.get("ingested_at", _now()),
            schema_version=d.get("schema_version", "1"),
        )


@dataclass
class Thread:
    """A group of related messages forming a conversation thread.

    Built by ThreadAssembler from raw messages using reply-chain
    and temporal proximity heuristics.
    """
    id: str = ""
    venue: str = ""
    venue_id: str = ""
    messages: list[Message] = field(default_factory=list)
    participant_ids: set[str] = field(default_factory=set)
    agent_participant_ids: set[str] = field(default_factory=set)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    message_count: int = 0
    topic: str = ""                       # Auto-detected or user-set topic

    def add_message(self, msg: Message) -> None:
        """Add a message and update thread metadata."""
        self.messages.append(msg)
        self.participant_ids.add(msg.sender_id)
        if msg.sender_agent_id:
            self.agent_participant_ids.add(msg.sender_agent_id)
        if not self.started_at or msg.timestamp < self.started_at:
            self.started_at = msg.timestamp
        if not self.ended_at or msg.timestamp > self.ended_at:
            self.ended_at = msg.timestamp
        self.message_count = len(self.messages)

    @property
    def duration(self) -> float:
        """Thread duration in seconds."""
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return 0.0

    @property
    def has_attachments(self) -> bool:
        """Whether any message in the thread has attachments."""
        return any(m.has_attachments for m in self.messages)

    def to_dict(self) -> dict[str, Any]:
        """Execute to dict operation."""
        d = asdict(self)
        d["participant_ids"] = list(self.participant_ids)
        d["agent_participant_ids"] = list(self.agent_participant_ids)
        return d
