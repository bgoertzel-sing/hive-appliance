"""Tests for conversation.types module."""
import time
from conversation.types import Message, Thread, ContentType, VenueType, _message_id


class TestMessageId:
    def test_deterministic(self):
        a = _message_id("tg", "123", "456")
        b = _message_id("tg", "123", "456")
        assert a == b
        assert a.startswith("msg_")

    def test_different_inputs_different_ids(self):
        a = _message_id("tg", "123", "456")
        b = _message_id("tg", "123", "789")
        assert a != b

    def test_prefix(self):
        mid = _message_id("slack", "C01", "ts123")
        assert mid.startswith("msg_")
        assert len(mid) == 4 + 16  # "msg_" + 16 hex chars


class TestMessage:
    def test_defaults(self):
        m = Message()
        assert m.id == ""
        assert m.content_type == ContentType.TEXT
        assert m.schema_version == "1"
        assert m.metadata == {}

    def test_auto_id(self):
        m = Message(venue="tg", venue_id="100", venue_message_id="42")
        assert m.id.startswith("msg_")

    def test_no_auto_id_without_venue(self):
        m = Message(content="hello")
        assert m.id == ""

    def test_roundtrip_dict(self):
        m = Message(
            venue=VenueType.TELEGRAM_GROUP,
            venue_id="group1",
            venue_message_id="99",
            sender_id="user1",
            sender_name="Alice",
            sender_agent_id="proto2",
            content="Hello world",
            reply_to_id="msg_prev",
            metadata={"edited": True},
        )
        d = m.to_dict()
        m2 = Message.from_dict(d)
        assert m2.id == m.id
        assert m2.venue == m.venue
        assert m2.content == m.content
        assert m2.sender_agent_id == m.sender_agent_id
        assert m2.metadata == {"edited": True}
        assert m2.reply_to_id == "msg_prev"

    def test_content_types(self):
        assert ContentType.TEXT == "text"
        assert ContentType.VOICE_TRANSCRIPT == "voice_transcript"
        assert ContentType.SYSTEM == "system"

    def test_venue_types(self):
        assert VenueType.TELEGRAM_GROUP == "telegram_group"
        assert VenueType.SLACK_CHANNEL == "slack_channel"
        assert VenueType.TRANSCRIPT_FILE == "transcript_file"


class TestThread:
    def test_empty(self):
        t = Thread(id="t1", venue="tg", venue_id="g1")
        assert t.message_count == 0
        assert t.participant_ids == set()

    def test_add_message(self):
        t = Thread(id="t1", venue="tg", venue_id="g1")
        m1 = Message(
            id="m1", venue="tg", venue_id="g1", venue_message_id="1",
            sender_id="u1", sender_name="Alice", timestamp=1000.0, content="hi"
        )
        m2 = Message(
            id="m2", venue="tg", venue_id="g1", venue_message_id="2",
            sender_id="u2", sender_name="Bob", sender_agent_id="agent1",
            timestamp=1001.0, content="hello"
        )
        t.add_message(m1)
        t.add_message(m2)
        assert t.message_count == 2
        assert t.participant_ids == {"u1", "u2"}
        assert t.agent_participant_ids == {"agent1"}
        assert t.started_at == 1000.0
        assert t.last_activity == 1001.0

    def test_started_at_tracks_earliest(self):
        t = Thread(id="t1", venue="tg", venue_id="g1")
        t.add_message(Message(id="m2", venue="tg", venue_id="g1",
                              venue_message_id="2", sender_id="u1",
                              timestamp=2000.0, content="later"))
        t.add_message(Message(id="m1", venue="tg", venue_id="g1",
                              venue_message_id="1", sender_id="u1",
                              timestamp=1000.0, content="earlier"))
        assert t.started_at == 1000.0
        assert t.last_activity == 2000.0
