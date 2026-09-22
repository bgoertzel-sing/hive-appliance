"""
SemanticIndex — ChromaDB-backed embedding search for the Conversation Store.

Provides vector similarity search over message content, enabling
"find conversations about X" queries across the entire hive corpus.
"""
from __future__ import annotations

import logging
from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import chromadb

from .types import Message

logger = logging.getLogger(__name__)

# Default collection name in ChromaDB
DEFAULT_COLLECTION = "hive_conversations"


class SemanticIndex:
    """Vector similarity search over conversation messages.

    Uses ChromaDB for storage and embedding generation. Messages are
    indexed by their content with venue/sender metadata for filtering.

    Usage:
        index = SemanticIndex()               # default collection
        index = SemanticIndex("my_collection") # custom collection
        index.index([msg1, msg2])             # add messages
        results = index.search("hive design", k=5)
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        persist_directory: str = "/hive/shared/conversation-store/chroma",
        client: chromadb.ClientAPI | None = None,
    ):
        import chromadb

        if client is not None:
            self._client = client
        else:
            self._client = chromadb.PersistentClient(path=persist_directory)

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection_name(self) -> str:
        """Return collection name."""
        return self._collection.name

    # ── write ────────────────────────────────────────────

    def index(self, messages: list[Message], batch_size: int = 100) -> int:
        """Add messages to the semantic index. Returns count indexed.

        Skips messages with empty content. Uses upsert for idempotency.
        """
        if not messages:
            return 0

        # Filter out empty-content messages
        valid = [m for m in messages if m.content.strip()]
        if not valid:
            return 0

        indexed = 0
        for i in range(0, len(valid), batch_size):
            batch = valid[i : i + batch_size]
            ids = [m.id for m in batch]
            documents = [m.content for m in batch]
            metadatas = [
                {
                    "venue": m.venue,
                    "venue_id": m.venue_id,
                    "sender_id": m.sender_id,
                    "sender_name": m.sender_name,
                    "sender_agent_id": m.sender_agent_id or "",
                    "timestamp": m.timestamp,
                    "content_type": m.content_type,
                    "thread_id": m.thread_id or "",
                }
                for m in batch
            ]
            try:
                self._collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
                indexed += len(batch)
            except Exception as e:
                logger.error("SemanticIndex.index batch %d failed: %s", i, e)
                raise

        return indexed

    # ── read ─────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: int = 10,
        venue: Optional[str] = None,
        venue_id: Optional[str] = None,
        sender_agent_id: Optional[str] = None,
        since: Optional[float] = None,
    ) -> list[dict]:
        """Semantic similarity search. Returns list of result dicts.

        Each result dict contains:
          - id: message ID
          - content: message text (document)
          - distance: cosine distance (lower = more similar)
          - metadata: venue, sender, timestamp, etc.
        """
        where_clauses: list[dict] = []
        if venue:
            where_clauses.append({"venue": {"$eq": venue}})
        if venue_id:
            where_clauses.append({"venue_id": {"$eq": venue_id}})
        if sender_agent_id:
            where_clauses.append({"sender_agent_id": {"$eq": sender_agent_id}})
        if since is not None:
            where_clauses.append({"timestamp": {"$gte": since}})

        where: dict | None = None
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}

        kwargs: dict = {
            "query_texts": [query],
            "n_results": k,
        }
        if where:
            kwargs["where"] = where

        try:
            results = self._collection.query(**kwargs)
        except Exception as e:
            logger.error("SemanticIndex.search failed: %s", e)
            raise

        # Flatten ChromaDB's nested result format
        items: list[dict] = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(ids)
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)

            for mid, doc, dist, meta in zip(ids, docs, dists, metas):
                items.append({
                    "id": mid,
                    "content": doc,
                    "distance": dist,
                    "metadata": meta,
                })

        return items

    # ── management ───────────────────────────────────────

    def count(self) -> int:
        """Total number of indexed messages."""
        return self._collection.count()

    def delete(self, message_ids: list[str]) -> None:
        """Remove messages from the index by ID."""
        if message_ids:
            self._collection.delete(ids=message_ids)

    def reset(self) -> None:
        """Delete and recreate the collection. USE WITH CAUTION."""
        name = self._collection.name
        meta = self._collection.metadata
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata=meta
        )
