"""Bootstrap — ingest historical transcripts into the Conversation Store.

Scans the hive for agent transcript files, parses them using
TranscriptFileCollector, and bulk-ingests into MessageStore + SemanticIndex.

Usage:
    from conversation.bootstrap import bootstrap_from_transcripts

    stats = bootstrap_from_transcripts(
        transcript_paths=["/hive/protomega2/transcript.txt"],
        db_path="/hive/shared/conversation-store/store.db",
        chroma_path="/hive/shared/conversation-store/chroma",
    )
    print(f"Ingested {stats['messages_added']} messages from {stats['files_processed']} files")
"""
from __future__ import annotations

import glob
import logging
import os
import time
from dataclasses import dataclass, field

from conversation.collectors.transcript_file import TranscriptFileCollector
from conversation.semantic import SemanticIndex
from conversation.store import DEFAULT_DB_PATH, MessageStore

logger = logging.getLogger(__name__)


# ── defaults ─────────────────────────────────────────────

DEFAULT_CHROMA_PATH = "/hive/shared/conversation-store/chroma"
DEFAULT_CHROMA_COLLECTION = "hive_conversations"

# Known agent transcript locations in the hive
HIVE_TRANSCRIPT_GLOBS = [
    "/hive/*/transcript.txt",
    "/hive/*/gateway/iter-agents/*/transcript.txt",
]

# Default agent_map: map common sender names to agent_ids
DEFAULT_AGENT_MAP = {
    "protomega2": "iter-protomega2",
    "protocosmo2": "iter-protocosmo2",
    "protomega": "iter-protomega",
    "protocosmo": "iter-protocosmo",
    "assistant": None,  # generic, don't assign
    "system": None,
}


@dataclass
class BootstrapStats:
    """Statistics from a bootstrap run."""
    files_found: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    messages_parsed: int = 0
    messages_added: int = 0
    messages_indexed: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "files_found": self.files_found,
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "files_failed": self.files_failed,
            "messages_parsed": self.messages_parsed,
            "messages_added": self.messages_added,
            "messages_indexed": self.messages_indexed,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
        }


def discover_transcripts(
    extra_paths: list[str] | None = None,
    globs: list[str] | None = None,
) -> list[str]:
    """Discover transcript files in the hive.

    Parameters
    ----------
    extra_paths:
        Additional explicit file paths to include.
    globs:
        Glob patterns to search. Defaults to HIVE_TRANSCRIPT_GLOBS.

    Returns
    -------
    list[str]
        Deduplicated list of existing transcript file paths.
    """
    if globs is None:
        globs = HIVE_TRANSCRIPT_GLOBS

    paths: set[str] = set()

    # From globs
    for pattern in globs:
        for match in glob.glob(pattern, recursive=False):
            if os.path.isfile(match):
                paths.add(os.path.realpath(match))

    # From explicit paths
    if extra_paths:
        for p in extra_paths:
            real = os.path.realpath(p)
            if os.path.isfile(real):
                paths.add(real)
            else:
                logger.warning("Transcript path not found: %s", p)

    return sorted(paths)


def _venue_id_from_path(path: str) -> str:
    """Derive a venue_id from a transcript file path.

    Heuristic: use the parent directory name (usually the agent name).
    Example: /hive/protomega2/transcript.txt → protomega2
    """
    parent = os.path.basename(os.path.dirname(path))
    return f"transcript_{parent}"


def bootstrap_from_transcripts(
    transcript_paths: list[str] | None = None,
    db_path: str = DEFAULT_DB_PATH,
    chroma_path: str = DEFAULT_CHROMA_PATH,
    collection_name: str = DEFAULT_CHROMA_COLLECTION,
    agent_map: dict[str, str | None] | None = None,
    batch_size: int = 200,
    index_batch_size: int = 100,
    skip_existing: bool = True,
) -> BootstrapStats:
    """Ingest historical transcript files into the Conversation Store.

    Parameters
    ----------
    transcript_paths:
        Explicit list of transcript file paths. If None, auto-discovers
        using HIVE_TRANSCRIPT_GLOBS.
    db_path:
        SQLite database path for MessageStore.
    chroma_path:
        ChromaDB persist directory for SemanticIndex.
    collection_name:
        ChromaDB collection name.
    agent_map:
        Mapping of sender names → agent_ids. Merged with DEFAULT_AGENT_MAP.
    batch_size:
        Number of messages to store per batch.
    index_batch_size:
        Number of messages to index per batch.
    skip_existing:
        If True, skip files whose venue_id already has messages in the store.

    Returns
    -------
    BootstrapStats
        Statistics about the bootstrap run.
    """
    start_time = time.time()
    stats = BootstrapStats()

    # Merge agent maps
    effective_agent_map = dict(DEFAULT_AGENT_MAP)
    if agent_map:
        effective_agent_map.update(agent_map)

    # Discover transcripts
    if transcript_paths is None:
        paths = discover_transcripts()
    else:
        paths = discover_transcripts(extra_paths=transcript_paths)

    stats.files_found = len(paths)
    logger.info("Found %d transcript files", stats.files_found)

    if not paths:
        stats.duration_seconds = time.time() - start_time
        return stats

    # Initialize store and index
    store = MessageStore(db_path)
    index = SemanticIndex(
        persist_directory=chroma_path,
        collection_name=collection_name,
    )

    for path in paths:
        venue_id = _venue_id_from_path(path)

        # Skip if already populated
        if skip_existing:
            existing = len(store.query(venue_id=venue_id, limit=1))
            if existing > 0:
                logger.info(
                    "Skipping %s — already has %d messages", path, existing
                )
                stats.files_skipped += 1
                continue

        logger.info("Processing %s as venue_id=%s", path, venue_id)

        try:
            collector = TranscriptFileCollector(
                path=path,
                venue_id=venue_id,
                agent_map=effective_agent_map,
            )

            # Collect all messages
            all_messages = collector.poll()
            stats.messages_parsed += len(all_messages)
            logger.info("  Parsed %d messages from %s", len(all_messages), path)

            # Batch insert into store
            for i in range(0, len(all_messages), batch_size):
                batch = all_messages[i : i + batch_size]
                added = store.append(batch)
                stats.messages_added += added

            # Batch index
            for i in range(0, len(all_messages), index_batch_size):
                batch = all_messages[i : i + index_batch_size]
                indexed = index.index(batch, batch_size=index_batch_size)
                stats.messages_indexed += indexed

            stats.files_processed += 1

        except Exception as e:
            logger.error("Failed to process %s: %s", path, e)
            stats.files_failed += 1
            stats.errors.append(f"{path}: {e}")

    stats.duration_seconds = time.time() - start_time
    logger.info(
        "Bootstrap complete: %d files processed, %d messages added, %.1fs",
        stats.files_processed,
        stats.messages_added,
        stats.duration_seconds,
    )

    return stats


def bootstrap_single_transcript(
    path: str,
    venue_id: str | None = None,
    store: MessageStore | None = None,
    index: SemanticIndex | None = None,
    agent_map: dict[str, str | None] | None = None,
) -> tuple[int, int]:
    """Ingest a single transcript file. Convenience wrapper.

    Parameters
    ----------
    path:
        Path to the transcript file.
    venue_id:
        Override venue_id. Defaults to derived from path.
    store:
        Existing MessageStore to use.
    index:
        Existing SemanticIndex to use.
    agent_map:
        Sender → agent_id mapping.

    Returns
    -------
    tuple[int, int]
        (messages_added_to_store, messages_indexed)
    """
    if venue_id is None:
        venue_id = _venue_id_from_path(path)

    effective_agent_map = dict(DEFAULT_AGENT_MAP)
    if agent_map:
        effective_agent_map.update(agent_map)

    collector = TranscriptFileCollector(
        path=path,
        venue_id=venue_id,
        agent_map=effective_agent_map,
    )

    messages = collector.poll()
    if not messages:
        return 0, 0

    if store is None:
        store = MessageStore()
    if index is None:
        index = SemanticIndex(
            persist_directory=DEFAULT_CHROMA_PATH,
            collection_name=DEFAULT_CHROMA_COLLECTION,
        )

    added = store.append(messages)
    indexed = index.index(messages)

    return added, indexed
