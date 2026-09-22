"""Pure adapter for structured Telegram Bot API message events."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from conversation.types import (
    Attachment, AttachmentType, ContentType, Message, VenueType,
)


@dataclass
class TelegramEventCollector:
    """Normalize already-received Telegram events without owning credentials."""

    account_id: str = "default"
    agent_map: dict[str, str] = field(default_factory=dict)

    def parse_message(self, event: dict[str, Any]) -> tuple[Message, list[Attachment]]:
        chat = event.get("chat") or {}
        sender = event.get("from") or {}
        message_id = str(event.get("message_id", ""))
        venue_id = str(chat.get("id", ""))
        venue = (VenueType.TELEGRAM_GROUP
                 if chat.get("type") in {"group", "supergroup"}
                 else VenueType.TELEGRAM_DM)
        media = self._media(event)
        message = Message(
            venue=venue,
            venue_id=venue_id,
            venue_message_id=message_id,
            sender_id=str(sender.get("id", "")),
            sender_name=(sender.get("username") or sender.get("first_name") or ""),
            sender_agent_id=self.agent_map.get(str(sender.get("id", ""))),
            timestamp=float(event.get("date", 0)),
            content=event.get("text") or event.get("caption") or "",
            content_type=ContentType.MEDIA_CAPTION if media else ContentType.TEXT,
            reply_to_id=(str((event.get("reply_to_message") or {}).get("message_id"))
                         if event.get("reply_to_message") else None),
            has_attachments=bool(media),
            metadata={"telegram_account_id": self.account_id},
        )
        attachments: list[Attachment] = []
        for kind, item in media:
            attachment = Attachment(
                message_id=message.id,
                venue=venue,
                venue_id=venue_id,
                attachment_type=kind,
                file_id=str(item.get("file_id", "")),
                file_unique_id=str(item.get("file_unique_id", "")),
                file_name=str(item.get("file_name", "")),
                file_size=int(item.get("file_size", 0) or 0),
                mime_type=str(item.get("mime_type", "")),
                width=item.get("width"),
                height=item.get("height"),
                duration=item.get("duration"),
                metadata={"telegram_account_id": self.account_id},
                created_at=message.timestamp,
            )
            attachments.append(attachment)
        message.attachment_ids = [attachment.id for attachment in attachments]
        return message, attachments

    @staticmethod
    def _media(event: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        for field_name, kind in (
            ("document", AttachmentType.DOCUMENT),
            ("audio", AttachmentType.AUDIO),
            ("video", AttachmentType.VIDEO),
            ("voice", AttachmentType.VOICE),
            ("animation", AttachmentType.ANIMATION),
            ("sticker", AttachmentType.STICKER),
        ):
            if event.get(field_name):
                return [(kind, event[field_name])]
        photos = event.get("photo") or []
        return [(AttachmentType.PHOTO, photos[-1])] if photos else []
