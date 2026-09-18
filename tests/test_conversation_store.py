"""Tests for conversation.store module (MessageStore with SQLite + FTS5)."""
import os
import tempfile
import time

import pytest

from conversation.types import Message, VenueType, ContentType
from conversation.store import MessageStore


@pytest.fixture
def tmp_db(tmp_path):
    """Yield a MessageStore backed by a temp SQLite file."""
    db = tmp_path / "test_messages.db"
    store = MessageStore(db)
    yield store
    store.close()


def _msg(venue_msg_id: str, content: str = "hello", **kw) -> Message:
    """Helper to build a Message with minimal required fields."""
    defaults = dict(
        venue=VenueType.TELEGRAM_GROUP,
        venue_id="group1",
        venue_message_id=venue_msg_id,
        sender_id="user1",
        sender_name="Alice",
        timestamp=time.time(),
        content=content,
    )
    defaults.update(kw)
    return Message(**defaults)


class TestAppend:
    def test_append_single(self, tmp_db):
        n = tmp_db.append([_msg("1")])
        assert n == 1
        assert tmp_db.count() == 1

    def test_append_multiple(self, tmp_db):
        n = tmp_db.append([_msg("1"), _msg("2"), _msg("3")])
        assert n == 3
        assert tmp_db.count() == 3

    def test_dedup(self, tmp_db):
        m = _msg("1")
        assert tmp_db.append([m]) == 1
        assert tmp_db.append([m]) == 0  # duplicate
        assert tmp_db.count() == 1

    def test_append_empty(self, tmp_db):
        assert tmp_db.append([]) == 0

    def test_mixed_dedup(self, tmp_db):
        tmp_db.append([_msg("1")])
        n = tmp_db.append([_msg("1"), _msg("2")])  # 1 dup + 1 new
        assert n == 1
        assert tmp_db.count() == 2


class TestGet:
    def test_get_existing(self, tmp_db):
        m = _msg("42", content="specific text")
        tmp_db.append([m])
        fetched = tmp_db.get(m.id)
        assert fetched is not None
        assert fetched.content == "specific text"
        assert fetched.venue_message_id == "42"

    def test_get_missing(self, tmp_db):
        assert tmp_db.get("nonexistent") is None

    def test_metadata_roundtrip(self, tmp_db):
        m = _msg("99", metadata={"edited": True, "forward_from": "other_chat"})
        tmp_db.append([m])
        fetched = tmp_db.get(m.id)
        assert fetched.metadata == {"edited": True, "forward_from": "other_chat"}


class TestQuery:
    def test_by_venue(self, tmp_db):
        tmp_db.append([
            _msg("1", venue=VenueType.TELEGRAM_GROUP),
            _msg("2", venue=VenueType.TELEGRAM_DM, venue_id="dm1"),
        ])
        tg = tmp_db.query(venue=VenueType.TELEGRAM_GROUP)
        assert len(tg) == 1
        dm = tmp_db.query(venue=VenueType.TELEGRAM_DM)
        assert len(dm) == 1

    def test_by_venue_id(self, tmp_db):
        tmp_db.append([
            _msg("1", venue_id="g1"),
            _msg("2", venue_id="g2"),
        ])
        assert len(tmp_db.query(venue_id="g1")) == 1

    def test_by_sender_agent(self, tmp_db):
        tmp_db.append([
            _msg("1", sender_agent_id="proto2"),
            _msg("2", sender_agent_id=None),
            _msg("3", sender_agent_id="cosmo2"),
        ])
        assert len(tmp_db.query(sender_agent_id="proto2")) == 1
        assert len(tmp_db.query(sender_agent_id="cosmo2")) == 1

    def test_time_range(self, tmp_db):
        base = 1000000.0
        tmp_db.append([
            _msg("1", timestamp=base),
            _msg("2", timestamp=base + 100),
            _msg("3", timestamp=base + 200),
        ])
        assert len(tmp_db.query(since=base + 50)) == 2
        assert len(tmp_db.query(until=base + 150)) == 2
        assert len(tmp_db.query(since=base + 50, until=base + 150)) == 1

    def test_limit_offset(self, tmp_db):
        msgs = [_msg(str(i), timestamp=1000.0 + i) for i in range(10)]
        tmp_db.append(msgs)
        page1 = tmp_db.query(limit=3, offset=0)
        page2 = tmp_db.query(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].venue_message_id != page2[0].venue_message_id

    def test_ordered_by_timestamp(self, tmp_db):
        tmp_db.append([
            _msg("late", timestamp=2000.0),
            _msg("early", timestamp=1000.0),
            _msg("mid", timestamp=1500.0),
        ])
        msgs = tmp_db.query()
        times = [m.timestamp for m in msgs]
        assert times == sorted(times)


class TestSearch:
    def test_basic_fts(self, tmp_db):
        tmp_db.append([
            _msg("1", content="The hive appliance handles infrastructure"),
            _msg("2", content="Weather forecast for tomorrow is sunny"),
            _msg("3", content="Hive conversation store design discussion"),
        ])
        results = tmp_db.search("hive")
        assert len(results) >= 2
        contents = [r.content for r in results]
        assert any("hive" in c.lower() for c in contents)

    def test_fts_with_venue_filter(self, tmp_db):
        tmp_db.append([
            _msg("1", content="hive topic in group", venue=VenueType.TELEGRAM_GROUP),
            _msg("2", content="hive topic in dm", venue=VenueType.TELEGRAM_DM, venue_id="dm1"),
        ])
        results = tmp_db.search("hive", venue=VenueType.TELEGRAM_GROUP)
        assert len(results) == 1
        assert results[0].venue == VenueType.TELEGRAM_GROUP

    def test_fts_no_results(self, tmp_db):
        tmp_db.append([_msg("1", content="nothing relevant here")])
        assert tmp_db.search("xyznonexistent") == []

    def test_fts_k_limit(self, tmp_db):
        for i in range(20):
            tmp_db.append([_msg(str(i), content=f"hive message number {i}")])
        results = tmp_db.search("hive", k=5)
        assert len(results) == 5


class TestCount:
    def test_count_empty(self, tmp_db):
        assert tmp_db.count() == 0

    def test_count_by_venue(self, tmp_db):
        tmp_db.append([
            _msg("1", venue=VenueType.TELEGRAM_GROUP),
            _msg("2", venue=VenueType.TELEGRAM_GROUP),
            _msg("3", venue=VenueType.TELEGRAM_DM, venue_id="dm1"),
        ])
        assert tmp_db.count() == 3
        assert tmp_db.count(venue=VenueType.TELEGRAM_GROUP) == 2
        assert tmp_db.count(venue=VenueType.TELEGRAM_DM) == 1


class TestVenues:
    def test_venues_listing(self, tmp_db):
        tmp_db.append([
            _msg("1", venue=VenueType.TELEGRAM_GROUP, venue_id="g1", timestamp=1000.0),
            _msg("2", venue=VenueType.TELEGRAM_GROUP, venue_id="g1", timestamp=2000.0),
            _msg("3", venue=VenueType.TELEGRAM_DM, venue_id="dm1", timestamp=1500.0),
        ])
        venues = tmp_db.venues()
        assert len(venues) == 2
        # Sorted by count desc: group has 2, dm has 1
        assert venues[0]["cnt"] == 2
        assert venues[0]["venue"] == VenueType.TELEGRAM_GROUP


class TestContentTypes:
    def test_voice_transcript(self, tmp_db):
        m = _msg("1", content="transcribed voice note", content_type=ContentType.VOICE_TRANSCRIPT)
        tmp_db.append([m])
        fetched = tmp_db.get(m.id)
        assert fetched.content_type == ContentType.VOICE_TRANSCRIPT

    def test_system_message(self, tmp_db):
        m = _msg("1", content="Alice joined the group", content_type=ContentType.SYSTEM)
        tmp_db.append([m])
        fetched = tmp_db.get(m.id)
        assert fetched.content_type == ContentType.SYSTEM


class TestReplyChain:
    def test_reply_to_stored(self, tmp_db):
        m1 = _msg("1", content="original")
        m2 = _msg("2", content="reply", reply_to_id=m1.id)
        tmp_db.append([m1, m2])
        fetched = tmp_db.get(m2.id)
        assert fetched.reply_to_id == m1.id

    def test_thread_id_filter(self, tmp_db):
        tmp_db.append([
            _msg("1", thread_id="t1", content="in thread"),
            _msg("2", thread_id="t1", content="also in thread"),
            _msg("3", thread_id=None, content="no thread"),
        ])
        threaded = tmp_db.query(thread_id="t1")
        assert len(threaded) == 2
