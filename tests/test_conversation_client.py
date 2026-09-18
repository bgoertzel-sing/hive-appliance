"""Tests for ConversationStoreClient — the unified agent query API."""
from __future__ import annotations

import os
import time
import tempfile

import pytest

from conversation.types import Message, VenueType, ContentType
from conversation.store import MessageStore
from conversation.semantic import SemanticIndex
from conversation.threading import ThreadAssembler
from conversation.client import ConversationStoreClient


# ── helpers ──────────────────────────────────────────────

def _msg(
    line: int,
    sender: str,
    content: str,
    ts: float,
    venue_id: str = "chat1",
    reply_to: str | None = None,
    agent_id: str | None = None,
) -> Message:
    return Message(
        venue=VenueType.TRANSCRIPT_FILE,
        venue_id=venue_id,
        venue_message_id=str(line),
        sender_id=sender,
        sender_name=sender,
        sender_agent_id=agent_id,
        timestamp=ts,
        content=content,
        content_type=ContentType.TEXT,
        reply_to_id=reply_to,
    )


BASE_TS = 1726660800.0  # 2024-09-18 12:00:00 UTC


# ── fixtures ─────────────────────────────────────────────

@pytest.fixture
def tmp_dirs(tmp_path):
    """Create temp directories for store and index."""
    db_path = str(tmp_path / "test.db")
    chroma_path = str(tmp_path / "chroma")
    os.makedirs(chroma_path, exist_ok=True)
    return db_path, chroma_path


@pytest.fixture
def client(tmp_dirs):
    """Create a ConversationStoreClient with temp backends."""
    db_path, chroma_path = tmp_dirs
    store = MessageStore(db_path)
    index = SemanticIndex(persist_directory=chroma_path, collection_name="test_conv")
    assembler = ThreadAssembler(gap_threshold_seconds=300, min_thread_messages=1)
    return ConversationStoreClient(store=store, index=index, assembler=assembler)


@pytest.fixture
def populated_client(client):
    """Client with sample messages already ingested."""
    messages = [
        _msg(1, "Alice", "Let's discuss the hive appliance architecture", BASE_TS, agent_id="agent_alice"),
        _msg(2, "Bob", "Sure, I think we should use event-driven design", BASE_TS + 30, agent_id="agent_bob"),
        _msg(3, "Alice", "Good idea. What about the reducer pattern?", BASE_TS + 60, agent_id="agent_alice", reply_to="2"),
        _msg(4, "Bob", "Reducers work great for state management", BASE_TS + 90, agent_id="agent_bob", reply_to="3"),
        # Gap — new topic
        _msg(5, "Charlie", "Hey, anyone available for a code review?", BASE_TS + 700),
        _msg(6, "Alice", "I can help with the review", BASE_TS + 720, agent_id="agent_alice"),
        # Different venue
        _msg(7, "Alice", "Private note about the project", BASE_TS + 100, venue_id="dm_alice", agent_id="agent_alice"),
        _msg(8, "Bot", "Acknowledged", BASE_TS + 110, venue_id="dm_alice", agent_id="agent_bot"),
    ]
    client.ingest(messages)
    return client


# ── ingest ───────────────────────────────────────────────

class TestIngest:
    def test_ingest_returns_count(self, client):
        msgs = [_msg(1, "A", "hello", BASE_TS)]
        assert client.ingest(msgs) == 1

    def test_ingest_deduplicates(self, client):
        msgs = [_msg(1, "A", "hello", BASE_TS)]
        client.ingest(msgs)
        assert client.ingest(msgs) == 0  # already exists

    def test_ingest_updates_both_store_and_index(self, client):
        msgs = [
            _msg(1, "A", "hello world", BASE_TS),
            _msg(2, "B", "goodbye world", BASE_TS + 10),
        ]
        client.ingest(msgs)
        stats = client.stats()
        assert stats["message_count"] == 2
        assert stats["index_count"] == 2


# ── search ───────────────────────────────────────────────

class TestSearch:
    def test_search_returns_threads(self, populated_client):
        threads = populated_client.search("architecture design", k=5)
        assert isinstance(threads, list)
        assert len(threads) > 0
        # threads contain Thread objects
        from conversation.threading import Thread
        assert all(isinstance(t, Thread) for t in threads)

    def test_search_raw_mode(self, populated_client):
        results = populated_client.search("architecture", k=5, as_threads=False)
        assert isinstance(results, list)
        if results:
            msg, dist = results[0]
            assert isinstance(msg, Message)
            assert isinstance(dist, float)

    def test_search_finds_relevant(self, populated_client):
        results = populated_client.search("reducer pattern state", k=5, as_threads=False)
        assert len(results) > 0
        contents = [m.content for m, _ in results]
        assert any("reducer" in c.lower() or "state" in c.lower() for c in contents)

    def test_search_with_venue_filter(self, populated_client):
        # Search only in dm venue
        threads = populated_client.search(
            "project", k=5, venue_id="dm_alice"
        )
        if threads:
            assert all(t.venue_id == "dm_alice" for t in threads)


# ── recent ───────────────────────────────────────────────

class TestRecent:
    def test_recent_returns_threads(self, populated_client):
        # All our test messages are old, so mock "recent" by using large hours
        threads = populated_client.recent(hours=999999)
        assert len(threads) > 0

    def test_recent_raw_mode(self, populated_client):
        messages = populated_client.recent(hours=999999, as_threads=False)
        assert isinstance(messages, list)
        assert all(isinstance(m, Message) for m in messages)

    def test_recent_venue_filter(self, populated_client):
        threads = populated_client.recent(venue_id="dm_alice", hours=999999)
        if threads:
            assert all(t.venue_id == "dm_alice" for t in threads)

    def test_recent_empty_when_no_match(self, populated_client):
        threads = populated_client.recent(
            venue_id="nonexistent", hours=999999
        )
        assert threads == []


# ── by_participant ───────────────────────────────────────

class TestByParticipant:
    def test_by_agent(self, populated_client):
        threads = populated_client.by_participant("agent_alice")
        assert len(threads) > 0
        # Alice should be in participants of each thread
        for t in threads:
            agent_msgs = [m for m in t.messages if m.sender_agent_id == "agent_alice"]
            assert len(agent_msgs) > 0

    def test_by_agent_raw_mode(self, populated_client):
        messages = populated_client.by_participant("agent_alice", as_threads=False)
        assert all(m.sender_agent_id == "agent_alice" for m in messages)

    def test_nonexistent_agent(self, populated_client):
        threads = populated_client.by_participant("agent_nobody")
        assert threads == []


# ── context_for ──────────────────────────────────────────

class TestContextFor:
    def test_context_returns_surrounding_messages(self, populated_client):
        # Get context for message 3 (Alice's reducer question)
        msg3_id = _msg(3, "Alice", "", BASE_TS + 60).id
        context = populated_client.context_for(msg3_id, window=5)
        assert len(context) > 0
        # Should include the target message
        ids = [m.id for m in context]
        assert msg3_id in ids

    def test_context_chronological(self, populated_client):
        msg3_id = _msg(3, "Alice", "", BASE_TS + 60).id
        context = populated_client.context_for(msg3_id, window=10)
        for i in range(1, len(context)):
            assert context[i].timestamp >= context[i-1].timestamp

    def test_context_nonexistent_message(self, populated_client):
        context = populated_client.context_for("nonexistent_id", window=10)
        assert context == []

    def test_context_window_size(self, populated_client):
        msg3_id = _msg(3, "Alice", "", BASE_TS + 60).id
        context = populated_client.context_for(msg3_id, window=3)
        assert len(context) <= 3


# ── full_text_search ─────────────────────────────────────

class TestFullTextSearch:
    def test_fts_finds_exact_terms(self, populated_client):
        results = populated_client.full_text_search("reducer", as_threads=False)
        assert len(results) > 0
        assert any("reducer" in m.content.lower() for m in results)

    def test_fts_as_threads(self, populated_client):
        threads = populated_client.full_text_search("architecture")
        assert isinstance(threads, list)

    def test_fts_venue_filter(self, populated_client):
        results = populated_client.full_text_search(
            "project", venue_id="dm_alice", as_threads=False
        )
        if results:
            assert all(m.venue_id == "dm_alice" for m in results)


# ── stats ────────────────────────────────────────────────

class TestStats:
    def test_empty_stats(self, client):
        stats = client.stats()
        assert stats["message_count"] == 0
        assert stats["index_count"] == 0

    def test_stats_after_ingest(self, populated_client):
        stats = populated_client.stats()
        assert stats["message_count"] == 8
        assert stats["index_count"] == 8
