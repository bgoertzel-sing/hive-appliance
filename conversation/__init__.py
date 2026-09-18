"""Hive Conversation Store — cross-agent, cross-venue message archive.

Components
----------
- **types**: Message, VenueType, ContentType dataclasses
- **store**: MessageStore (SQLite + FTS5 persistence)
- **semantic**: SemanticIndex (ChromaDB vector search)
- **collectors**: VenueCollector protocol, TranscriptFileCollector
- **threading**: Thread, ThreadAssembler (hybrid reply-chain + temporal)
- **client**: ConversationStoreClient (unified agent query API)
- **bootstrap**: bootstrap_from_transcripts (historical ingest)
"""
