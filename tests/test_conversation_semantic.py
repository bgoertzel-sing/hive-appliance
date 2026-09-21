"""Tests for conversation.semantic module (SemanticIndex with ChromaDB)."""
import time

import pytest

from conversation.semantic import SemanticIndex
from conversation.types import Message, VenueType


@pytest.fixture
def sem_index(tmp_path):
    """Yield a SemanticIndex backed by a temp ChromaDB directory."""
    idx = SemanticIndex(
        collection_name="test_conversations",
        persist_directory=str(tmp_path / "chroma"),
    )
    yield idx


def _msg(venue_msg_id: str, content: str = "hello", **kw) -> Message:
    """Helper to build a Message with minimal required fields."""
    defaults = {
        "venue": VenueType.TELEGRAM_GROUP,
        "venue_id": "group1",
        "venue_message_id": venue_msg_id,
        "sender_id": "user1",
        "sender_name": "Alice",
        "timestamp": time.time(),
        "content": content,
    }
    defaults.update(kw)
    return Message(**defaults)


class TestIndex:
    def test_index_single(self, sem_index):
        n = sem_index.index([_msg("1", content="test message")])
        assert n == 1
        assert sem_index.count() == 1

    def test_index_multiple(self, sem_index):
        msgs = [_msg(str(i), content=f"message {i}") for i in range(5)]
        n = sem_index.index(msgs)
        assert n == 5
        assert sem_index.count() == 5

    def test_index_empty(self, sem_index):
        assert sem_index.index([]) == 0

    def test_index_skips_empty_content(self, sem_index):
        msgs = [
            _msg("1", content="has content"),
            _msg("2", content=""),
            _msg("3", content="   "),
        ]
        n = sem_index.index(msgs)
        assert n == 1  # only the one with actual content

    def test_index_idempotent(self, sem_index):
        m = _msg("1", content="repeated message")
        sem_index.index([m])
        sem_index.index([m])  # upsert — should not duplicate
        assert sem_index.count() == 1

    def test_index_batching(self, sem_index):
        msgs = [_msg(str(i), content=f"batch msg {i}") for i in range(25)]
        n = sem_index.index(msgs, batch_size=10)
        assert n == 25
        assert sem_index.count() == 25


class TestSearch:
    def test_basic_search(self, sem_index):
        sem_index.index([
            _msg("1", content="The hive appliance monitors infrastructure health"),
            _msg("2", content="Weather forecast shows sunny skies tomorrow"),
            _msg("3", content="Discussion about hive conversation store design"),
        ])
        results = sem_index.search("hive infrastructure")
        assert len(results) > 0
        # The hive-related messages should rank higher
        assert any("hive" in r["content"].lower() for r in results[:2])

    def test_search_returns_metadata(self, sem_index):
        sem_index.index([_msg("1", content="metadata test message",
                              sender_agent_id="proto2")])
        results = sem_index.search("metadata test")
        assert len(results) == 1
        r = results[0]
        assert "id" in r
        assert "content" in r
        assert "distance" in r
        assert "metadata" in r
        assert r["metadata"]["venue"] == VenueType.TELEGRAM_GROUP
        assert r["metadata"]["sender_agent_id"] == "proto2"

    def test_search_k_limit(self, sem_index):
        msgs = [_msg(str(i), content=f"similar message about hive topic {i}")
                for i in range(20)]
        sem_index.index(msgs)
        results = sem_index.search("hive topic", k=5)
        assert len(results) == 5

    def test_search_no_results_empty_index(self, sem_index):
        results = sem_index.search("anything")
        assert results == []

    def test_search_venue_filter(self, sem_index):
        sem_index.index([
            _msg("1", content="group hive discussion",
                 venue=VenueType.TELEGRAM_GROUP),
            _msg("2", content="dm hive discussion",
                 venue=VenueType.TELEGRAM_DM, venue_id="dm1"),
        ])
        results = sem_index.search("hive discussion",
                                   venue=VenueType.TELEGRAM_GROUP)
        assert len(results) == 1
        assert results[0]["metadata"]["venue"] == VenueType.TELEGRAM_GROUP

    def test_search_agent_filter(self, sem_index):
        sem_index.index([
            _msg("1", content="proto2 says hello", sender_agent_id="proto2"),
            _msg("2", content="cosmo2 says hello", sender_agent_id="cosmo2"),
            _msg("3", content="human says hello"),
        ])
        results = sem_index.search("says hello", sender_agent_id="proto2")
        assert len(results) == 1
        assert results[0]["metadata"]["sender_agent_id"] == "proto2"

    def test_search_time_filter(self, sem_index):
        base = 1000000.0
        sem_index.index([
            _msg("1", content="old message about hive", timestamp=base),
            _msg("2", content="new message about hive", timestamp=base + 10000),
        ])
        results = sem_index.search("hive", since=base + 5000)
        assert len(results) == 1
        assert results[0]["metadata"]["timestamp"] >= base + 5000


class TestManagement:
    def test_count_empty(self, sem_index):
        assert sem_index.count() == 0

    def test_delete(self, sem_index):
        m1 = _msg("1", content="keep this")
        m2 = _msg("2", content="delete this")
        sem_index.index([m1, m2])
        assert sem_index.count() == 2
        sem_index.delete([m2.id])
        assert sem_index.count() == 1

    def test_reset(self, sem_index):
        sem_index.index([_msg(str(i), content=f"msg {i}") for i in range(5)])
        assert sem_index.count() == 5
        sem_index.reset()
        assert sem_index.count() == 0

    def test_collection_name(self, sem_index):
        assert sem_index.collection_name == "test_conversations"
