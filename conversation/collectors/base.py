"""Base VenueCollector protocol and helpers."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from conversation.types import Message


@runtime_checkable
class VenueCollector(Protocol):
    """Collects messages from a specific venue and normalizes them into Message records.

    Each collector knows how to poll a single venue type (Telegram group,
    Slack channel, transcript file, etc.) and yield Messages in chronological
    order.  Collectors are idempotent: re-polling with the same ``since_id``
    must not produce duplicates (the MessageStore deduplicates on append
    anyway, but collectors should avoid unnecessary work).
    """

    @property
    def venue_type(self) -> str:
        """Venue type identifier (e.g. 'telegram_group')."""
        ...

    @property
    def venue_id(self) -> str:
        """Venue-specific chat/channel identifier."""
        ...

    def poll(self, since_id: Optional[str] = None) -> list[Message]:
        """Fetch new messages since *since_id* (exclusive).

        Parameters
        ----------
        since_id:
            The venue_message_id of the last known message.  If ``None``,
            return all available messages.

        Returns
        -------
        list[Message]
            New messages in chronological order (oldest first).
        """
        ...
