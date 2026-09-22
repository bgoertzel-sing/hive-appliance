"""Hive Conversation Store — cross-agent, cross-venue message archive.

Components
----------
- **types**: Message, VenueType, ContentType, Attachment, AttachmentType, DownloadStatus
- **store**: MessageStore (SQLite + FTS5)
- **semantic**: SemanticIndex (ChromaDB vector search)
- **collectors**: VenueCollector protocol + TranscriptFileCollector
- **threading**: ThreadAssembler (reply-chain + temporal grouping)
- **attachments**: AttachmentStore, SharedFolderManager, AttachmentDownloadManager
- **client**: ConversationStoreClient (unified query API)
- **bootstrap**: Historical transcript ingestion
"""

from .types import (
    Attachment,
    AttachmentType,
    ContentType,
    DownloadStatus,
    Message,
    Thread,
    VenueType,
)
from .attachments import (
    AttachmentDownloader,
    AttachmentDownloadManager,
    AttachmentStore,
    SharedFolderManager,
)

__all__ = [
    "Attachment",
    "AttachmentDownloader",
    "AttachmentDownloadManager",
    "AttachmentStore",
    "AttachmentType",
    "ContentType",
    "DownloadStatus",
    "Message",
    "SharedFolderManager",
    "Thread",
    "VenueType",
]
