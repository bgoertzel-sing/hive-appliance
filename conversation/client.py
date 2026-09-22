"""ConversationStoreClient — unified query API for agents.

Combines MessageStore, SemanticIndex, and ThreadAssembler into a single
high-level interface that agents use to query the Conversation Store.

Usage:
    client = ConversationStoreClient()
    threads = client.search("hive appliance design", k=5)
    recent = client.recent(venue_id="protomega2_group", hours=24)
    context = client.context_for(message_id="tg_group_12345", window=20)
    threads = client.by_participant(agent_id="protomega2")
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from conversation.attachments import (
    AttachmentDownloadManager,
    AttachmentStore,
    SharedFolderManager,
)
from conversation.semantic import SemanticIndex
from conversation.store import MessageStore
from conversation.threading import Thread, ThreadAssembler
from conversation.types import Attachment, Message

# ── defaults ─────────────────────────────────────────────

DEFAULT_CHROMA_PATH = "/hive/shared/conversation-store/chroma"
DEFAULT_CHROMA_COLLECTION = "hive_conversations"


def _dict_to_message(d: dict) -> Message:
    """Convert a SemanticIndex result dict back into a Message.

    Preserves the canonical message ID from the index (which is the same
    deterministic ID used in MessageStore). Restores all venue coordinates
    and provenance from stored metadata.
    """
    meta = d.get("metadata", {})
    return Message(
        id=d.get("id", ""),  # CS02: preserve canonical ID
        venue=meta.get("venue", ""),
        venue_id=meta.get("venue_id", ""),
        venue_message_id=meta.get("venue_message_id", ""),
        sender_id=meta.get("sender_id", ""),
        sender_name=meta.get("sender_name", ""),
        sender_agent_id=meta.get("sender_agent_id") or None,
        timestamp=meta.get("timestamp", 0.0),
        content=d.get("content", ""),
        content_type=meta.get("content_type", "text"),
        thread_id=meta.get("thread_id") or None,
        reply_to_id=meta.get("reply_to_id") or None,
    )


@dataclass
class ConversationStoreClient:
    """High-level query interface for the Conversation Store.

    Wraps MessageStore (structured queries), SemanticIndex (vector search),
    and ThreadAssembler (thread grouping) into a single API.

    Parameters
    ----------
    store:
        MessageStore instance.  Created with defaults if not provided.
    index:
        SemanticIndex instance.  Created with defaults if not provided.
    assembler:
        ThreadAssembler instance.  Created with defaults if not provided.
    """
    store: Optional[MessageStore] = None
    index: Optional[SemanticIndex] = None
    assembler: Optional[ThreadAssembler] = None
    attachment_store: Optional[AttachmentStore] = None
    folder_manager: Optional[SharedFolderManager] = None
    download_manager: Optional[AttachmentDownloadManager] = None

    def __post_init__(self):
        if self.store is None:
            self.store = MessageStore()
        if self.index is None:
            self.index = SemanticIndex(
                persist_directory=DEFAULT_CHROMA_PATH,
                collection_name=DEFAULT_CHROMA_COLLECTION,
            )
        if self.assembler is None:
            self.assembler = ThreadAssembler()
        if self.attachment_store is None:
            self.attachment_store = AttachmentStore()
        if self.folder_manager is None:
            self.folder_manager = SharedFolderManager()
        if self.download_manager is None:
            self.download_manager = AttachmentDownloadManager(
                self.attachment_store,
                self.folder_manager,
            )

    # ── primary query methods ────────────────────────────

    def search(
        self,
        query: str,
        k: int = 10,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        as_threads: bool = True,
    ) -> list[Thread] | list[tuple[Message, float]]:
        """Semantic search over conversation history.

        Parameters
        ----------
        query:
            Natural language search query.
        k:
            Maximum number of matching messages to retrieve.
        venue:
            Filter by venue type.
        venue_id:
            Filter by specific venue/chat ID.
        since:
            Only messages after this UTC epoch timestamp.
        until:
            Only messages before this UTC epoch timestamp.
        as_threads:
            If True (default), group results into Threads.
            If False, return raw (Message, distance) pairs.

        Returns
        -------
        list[Thread] or list[tuple[Message, float]]
            Threads containing matching messages, or raw matches.
        """
        # SemanticIndex.search supports: query, k, venue, venue_id,
        # sender_agent_id, since — but NOT until.
        # We apply 'until' as a post-filter.
        results = self.index.search(
            query=query,
            k=k,
            venue=venue,
            venue_id=venue_id,
            since=since,
        )

        # Convert dicts → (Message, distance) pairs
        pairs: list[tuple[Message, float]] = []
        for d in results:
            msg = _dict_to_message(d)
            dist = d.get("distance", 0.0)
            # Post-filter by 'until'
            if until is not None and msg.timestamp > until:
                continue
            pairs.append((msg, dist))

        if not as_threads:
            return pairs

        messages = [msg for msg, _dist in pairs]
        return self.assembler.assemble(messages)

    def recent(
        self,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        hours: float = 24,
        limit: int = 500,
        as_threads: bool = True,
    ) -> list[Thread] | list[Message]:
        """Get recent messages, optionally grouped into threads.

        Parameters
        ----------
        venue:
            Filter by venue type.
        venue_id:
            Filter by specific venue/chat ID.
        hours:
            How far back to look (default: 24 hours).
        limit:
            Maximum messages to return.
        as_threads:
            If True (default), group into Threads.

        Returns
        -------
        list[Thread] or list[Message]
        """
        since = time.time() - (hours * 3600)
        messages = self.store.query(
            venue=venue,
            venue_id=venue_id,
            since=since,
            limit=limit,
        )

        if not as_threads:
            return messages

        return self.assembler.assemble(messages)

    def by_participant(
        self,
        agent_id: str,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 200,
        as_threads: bool = True,
    ) -> list[Thread] | list[Message]:
        """Get messages by a specific agent, optionally as threads.

        Parameters
        ----------
        agent_id:
            The agent_id to filter on (sender_agent_id field).
        venue:
            Filter by venue type.
        venue_id:
            Filter by specific venue/chat ID.
        since:
            Only messages after this UTC epoch timestamp.
        limit:
            Maximum messages.
        as_threads:
            If True, group into Threads.

        Returns
        -------
        list[Thread] or list[Message]
        """
        messages = self.store.query(
            venue=venue,
            venue_id=venue_id,
            sender_agent_id=agent_id,
            since=since,
            limit=limit,
        )

        if not as_threads:
            return messages

        return self.assembler.assemble(messages)

    def context_for(
        self,
        message_id: str,
        window: int = 20,
    ) -> list[Message]:
        """Get surrounding context for a specific message.

        Fetches the target message, then retrieves nearby messages
        from the same venue_id within a time window.

        Parameters
        ----------
        message_id:
            The message ID to get context for.
        window:
            Number of messages to include (centered on target).

        Returns
        -------
        list[Message]
            Messages surrounding the target, in chronological order.
        """
        target = self.store.get(message_id)
        if target is None:
            return []

        # Get messages around the target timestamp
        half_window = window // 2
        # Query before the target
        before = self.store.query(
            venue_id=target.venue_id,
            until=target.timestamp + 0.001,
            limit=half_window + 1,
        )
        # Query after the target
        after = self.store.query(
            venue_id=target.venue_id,
            since=target.timestamp - 0.001,
            limit=half_window + 1,
        )

        # Merge and dedup
        seen: set[str] = set()
        combined: list[Message] = []
        for msg in before + after:
            if msg.id not in seen:
                seen.add(msg.id)
                combined.append(msg)

        # Sort by timestamp
        combined.sort(key=lambda m: m.timestamp)

        # Trim to window size, centered on target
        target_idx = next(
            (i for i, m in enumerate(combined) if m.id == message_id),
            len(combined) // 2,
        )
        start = max(0, target_idx - half_window)
        end = min(len(combined), start + window)
        start = max(0, end - window)

        return combined[start:end]

    def full_text_search(
        self,
        query: str,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        limit: int = 50,
        as_threads: bool = True,
    ) -> list[Thread] | list[Message]:
        """Full-text search using SQLite FTS5.

        Unlike semantic search, this does exact keyword matching.

        Parameters
        ----------
        query:
            FTS5 search query (supports AND, OR, NOT, phrases).
        venue:
            Filter by venue type.
        venue_id:
            Filter by specific venue/chat ID.
        limit:
            Maximum results.
        as_threads:
            If True, group into Threads.

        Returns
        -------
        list[Thread] or list[Message]
        """
        messages = self.store.search(query, k=limit)

        # Apply venue filters
        if venue:
            messages = [m for m in messages if m.venue == venue]
        if venue_id:
            messages = [m for m in messages if m.venue_id == venue_id]

        if not as_threads:
            return messages

        return self.assembler.assemble(messages)

    # ── ingestion helpers ────────────────────────────────

    def ingest(self, messages: list[Message]) -> int:
        """Ingest messages into both store and semantic index.

        Parameters
        ----------
        messages:
            Messages to ingest.

        Returns
        -------
        int
            Number of new messages added to the store.
        """
        count = self.store.append(messages)
        # Index all (SemanticIndex upserts, so duplicates are fine)
        self.index.index(messages)
        return count

    # ── attachment methods ────────────────────────────────

    def ingest_attachment(self, attachment: Attachment) -> bool:
        """Register an attachment for download.

        Parameters
        ----------
        attachment:
            Attachment metadata to store and optionally download.

        Returns
        -------
        bool
            True if enqueued successfully.
        """
        return self.download_manager.enqueue(attachment)

    def ingest_attachments(self, attachments: list[Attachment]) -> int:
        """Register multiple attachments for download.

        Returns count successfully enqueued.
        """
        count = 0
        for att in attachments:
            if self.download_manager.enqueue(att):
                count += 1
        return count

    def attachments_for_message(self, message_id: str) -> list[Attachment]:
        """Get all attachments for a message.

        Parameters
        ----------
        message_id:
            The message ID to look up attachments for.

        Returns
        -------
        list[Attachment]
        """
        return self.attachment_store.by_message(message_id)

    def attachments_for_venue(
        self,
        venue: str = "",
        venue_id: str = "",
        attachment_type: str = "",
        limit: int = 100,
    ) -> list[Attachment]:
        """Query attachments by venue, optionally filtered by type.

        Parameters
        ----------
        venue:
            Filter by venue type (e.g. "telegram_group").
        venue_id:
            Filter by specific venue/chat ID.
        attachment_type:
            Filter by AttachmentType (e.g. "photo", "document").
        limit:
            Maximum results.

        Returns
        -------
        list[Attachment]
        """
        return self.attachment_store.by_venue(
            venue=venue,
            venue_id=venue_id,
            limit=limit,
            attachment_type=attachment_type,
        )

    def process_pending_downloads(self, batch_size: int = 10) -> list[dict]:
        """Process pending attachment downloads.

        Returns a list of result dicts with 'id', 'success', and
        'path' or 'error' keys.
        """
        return self.download_manager.process_pending(batch_size=batch_size)

    def retry_failed_downloads(self, batch_size: int = 10) -> list[dict]:
        """Retry previously failed attachment downloads."""
        return self.download_manager.retry_failed(batch_size=batch_size)

    def attachment_stats(self) -> dict:
        """Return attachment statistics.

        Returns
        -------
        dict
            Keys: total, completed, pending, failed, skipped,
            downloaded_bytes, downloaded_mb.
        """
        return self.attachment_store.stats()

    def folder_disk_usage(self) -> dict:
        """Return disk usage of the shared attachments folder."""
        return self.folder_manager.disk_usage()

    # ── stats ────────────────────────────────────────────

    def stats(self) -> dict:
        """Return basic statistics about the store.

        Returns
        -------
        dict
            Keys: message_count, index_count.
        """
        result = {
            "message_count": self.store.count(),
            "index_count": self.index.count(),
        }
        try:
            result["attachments"] = self.attachment_store.stats()
        except Exception:
            result["attachments"] = {"error": "unavailable"}
        return result
