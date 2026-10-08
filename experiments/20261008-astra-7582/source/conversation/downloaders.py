"""DownloaderRegistry — maps venue types to platform downloaders.

AF01: Provides a central registry so the DownloadManager can automatically
select the correct downloader for each attachment's venue type.
"""
from __future__ import annotations

import logging
from typing import Optional

from conversation.attachments import AttachmentDownloader

logger = logging.getLogger(__name__)


class DownloaderRegistry:
    """Registry mapping venue types to downloader implementations.

    Usage:
        registry = DownloaderRegistry()
        registry.register("telegram_group", TelegramDownloader(bot_token))
        downloader = registry.get("telegram_group")
    """

    def __init__(self) -> None:
        self._downloaders: dict[str, AttachmentDownloader] = {}

    def register(self, venue_type: str, downloader: AttachmentDownloader) -> None:
        """Register a downloader for a venue type."""
        self._downloaders[venue_type] = downloader
        logger.info("Registered downloader for venue type %s", venue_type)

    def get(self, venue_type: str) -> Optional[AttachmentDownloader]:
        """Get the downloader for a venue type, or None."""
        return self._downloaders.get(venue_type)

    def has(self, venue_type: str) -> bool:
        """Check if a downloader is registered for a venue type."""
        return venue_type in self._downloaders

    @property
    def venue_types(self) -> list[str]:
        """List registered venue types."""
        return list(self._downloaders.keys())
