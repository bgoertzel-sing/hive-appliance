"""TelegramCollector — collect messages + attachments from Telegram groups.

AF01: Provides end-to-end ingestion from Telegram into the Conversation Store,
including attachment metadata extraction and platform downloader integration.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from conversation.types import (
    Attachment,
    AttachmentType,
    ContentType,
    Message,
    VenueType,
)
from conversation.collectors.base import VenueCollector

logger = logging.getLogger(__name__)

# Map Telegram attachment types to our AttachmentType
_TG_TYPE_MAP = {
    "photo": AttachmentType.PHOTO,
    "document": AttachmentType.DOCUMENT,
    "video": AttachmentType.VIDEO,
    "audio": AttachmentType.AUDIO,
    "voice": AttachmentType.VOICE,
    "video_note": AttachmentType.VIDEO_NOTE,
    "sticker": AttachmentType.STICKER,
    "animation": AttachmentType.ANIMATION,
}


class TelegramCollector:
    """Collects messages from a Telegram group/channel.

    Implements VenueCollector protocol. Requires a Telegram Bot API
    client for actual polling.

    Parameters
    ----------
    chat_id : str
        Telegram chat ID (group/channel).
    bot_token : str
        Telegram Bot API token.
    api_client : optional
        Pre-configured API client (for testing/injection).
    """

    def __init__(
        self,
        chat_id: str,
        bot_token: str = "",
        api_client: Any = None,
    ):
        self._chat_id = chat_id
        self._bot_token = bot_token
        self._api_client = api_client
        self._venue = VenueType.TELEGRAM_GROUP

    @property
    def venue_type(self) -> str:
        return self._venue

    @property
    def venue_id(self) -> str:
        return self._chat_id

    def poll(self, since_id: Optional[str] = None) -> list[Message]:
        """Fetch new messages from Telegram.

        Parameters
        ----------
        since_id : optional
            The venue_message_id of the last known message.

        Returns
        -------
        list[Message]
            New messages with attachment metadata populated.
        """
        if self._api_client is None:
            logger.warning("No Telegram API client configured")
            return []

        raw_messages = self._api_client.get_updates(
            chat_id=self._chat_id,
            offset=int(since_id) + 1 if since_id else None,
        )

        results = []
        for raw in raw_messages:
            msg = self._normalize(raw)
            if msg:
                results.append(msg)

        return results

    def _normalize(self, raw: dict) -> Optional[Message]:
        """Convert a raw Telegram message dict to a Message record."""
        msg_id = str(raw.get("message_id", ""))
        if not msg_id:
            return None

        # Build sender info
        from_user = raw.get("from", {})
        sender_id = str(from_user.get("id", ""))
        sender_name = from_user.get("first_name", "")
        if from_user.get("last_name"):
            sender_name += " " + from_user["last_name"]

        # Content
        content = raw.get("text", "") or raw.get("caption", "") or ""
        content_type = ContentType.TEXT

        # Reply
        reply_to = raw.get("reply_to_message", {})
        reply_to_id = ""
        if reply_to:
            reply_to_id = f"tg_{self._chat_id}_{reply_to.get('message_id', '')}"

        # Timestamp
        ts = float(raw.get("date", time.time()))

        msg = Message(
            id=f"tg_{self._chat_id}_{msg_id}",
            venue=self._venue,
            venue_id=self._chat_id,
            venue_message_id=msg_id,
            sender_id=sender_id,
            sender_name=sender_name,
            timestamp=ts,
            content=content,
            content_type=content_type,
            reply_to_id=reply_to_id,
            metadata={"raw_message_id": int(msg_id)} if msg_id.isdigit() else {},
        )

        # Extract attachment metadata
        msg.attachment_ids = []
        msg.has_attachments = False
        for tg_type, att_type in _TG_TYPE_MAP.items():
            att_data = raw.get(tg_type)
            if att_data:
                msg.has_attachments = True
                if tg_type == "photo":
                    # Telegram sends multiple sizes; use the largest
                    if isinstance(att_data, list) and att_data:
                        att_data = att_data[-1]
                att = self._extract_attachment(msg.id, att_data, att_type, tg_type)
                if att:
                    msg.attachment_ids.append(att.id)
                    if not hasattr(msg, "_extracted_attachments"):
                        msg._extracted_attachments = []
                    msg._extracted_attachments.append(att)

        return msg

    def _extract_attachment(
        self, message_id: str, data: dict, att_type: str, tg_type: str
    ) -> Optional[Attachment]:
        """Extract an Attachment record from Telegram file metadata."""
        if not isinstance(data, dict):
            return None

        file_id = data.get("file_id", "")
        if not file_id:
            return None

        return Attachment(
            message_id=message_id,
            attachment_type=att_type,
            file_id=file_id,
            file_unique_id=data.get("file_unique_id", ""),
            file_name=data.get("file_name", ""),
            file_size=data.get("file_size", 0),
            mime_type=data.get("mime_type", ""),
            duration=data.get("duration"),
            width=data.get("width"),
            height=data.get("height"),
        )

    def get_attachments(self, message: Message) -> list[Attachment]:
        """Return extracted attachments for a message."""
        return getattr(message, "_extracted_attachments", [])
