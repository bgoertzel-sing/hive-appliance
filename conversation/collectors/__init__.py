"""Venue collectors for the Conversation Store."""
from .base import VenueCollector
from .transcript_file import TranscriptFileCollector

__all__ = ["VenueCollector", "TranscriptFileCollector"]

# Optional: Telegram collector (requires API client)
try:
    from .telegram import TelegramCollector
    __all__.append("TelegramCollector")
except ImportError:
    pass
