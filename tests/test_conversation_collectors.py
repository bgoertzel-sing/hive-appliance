"""Tests for conversation venue collectors."""
from __future__ import annotations

import os
import tempfile
import time

import pytest

from conversation.types import Message, VenueType, ContentType
from conversation.collectors.base import VenueCollector
from conversation.collectors.transcript_file import TranscriptFileCollector


# ── fixtures ─────────────────────────────────────────────

SAMPLE_TRANSCRIPT = """\
[2026-09-18 10:00:00] Alice: Hello everyone
[2026-09-18 10:00:15] Bob: Hi Alice! How are you?
[2026-09-18 10:01:00] Alice: I'm working on the hive appliance.
It's going well so far.
[2026-09-18 10:02:00] Charlie: joined the chat
[2026-09-18 10:03:00] Alice: Let me share the status update:
- M1 done
- M2 done
- M3 done
[2026-09-18 10:05:00] Bob: Great progress!
"""

EDGE_CASE_TRANSCRIPT = """\
[2026-09-18 08:00:00] System: pinned a message
[2026-09-18 08:01:00] User With Spaces: message content here
[2026-09-18 08:02:00] Bot: Hello! Here's a link: https://example.com/path?q=1&r=2
[2026-09-18 08:03:00] Unicode™User: Héllo wörld 🌍
[2026-09-18 08:04:00] Empty: 
"""

EMPTY_FILE = ""
BLANK_LINES_ONLY = "\n\n\n"


@pytest.fixture
def sample_transcript(tmp_path):
    """Write sample transcript to a temp file."""
    p = tmp_path / "transcript.txt"
    p.write_text(SAMPLE_TRANSCRIPT)
    return str(p)


@pytest.fixture
def edge_case_transcript(tmp_path):
    """Write edge case transcript to a temp file."""
    p = tmp_path / "edge_cases.txt"
    p.write_text(EDGE_CASE_TRANSCRIPT)
    return str(p)


@pytest.fixture
def empty_transcript(tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text(EMPTY_FILE)
    return str(p)


@pytest.fixture
def blank_transcript(tmp_path):
    p = tmp_path / "blank.txt"
    p.write_text(BLANK_LINES_ONLY)
    return str(p)


# ── protocol conformance ─────────────────────────────────

class TestVenueCollectorProtocol:
    def test_transcript_collector_is_venue_collector(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        assert isinstance(collector, VenueCollector)

    def test_venue_type(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        assert collector.venue_type == VenueType.TRANSCRIPT_FILE

    def test_venue_id_defaults_to_filename(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        assert collector.venue_id == "transcript"

    def test_venue_id_custom(self, sample_transcript):
        collector = TranscriptFileCollector(
            path=sample_transcript, venue_id="protomega2"
        )
        assert collector.venue_id == "protomega2"


# ── basic parsing ────────────────────────────────────────

class TestTranscriptParsing:
    def test_parse_sample_messages(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        assert len(messages) == 6

    def test_first_message_fields(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        msg = messages[0]
        assert msg.sender_name == "Alice"
        assert msg.content == "Hello everyone"
        assert msg.venue == VenueType.TRANSCRIPT_FILE
        assert msg.content_type == ContentType.TEXT

    def test_multiline_message(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        # Alice's "I'm working on..." is multi-line
        alice_working = messages[2]
        assert alice_working.sender_name == "Alice"
        assert "hive appliance" in alice_working.content
        assert "going well" in alice_working.content

    def test_multiline_with_list(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        # Alice's status update with bullet list
        status = messages[4]
        assert status.sender_name == "Alice"
        assert "- M1 done" in status.content
        assert "- M3 done" in status.content

    def test_system_message_detection(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        # "Charlie: joined the chat" should be detected as system
        charlie = messages[3]
        assert charlie.sender_name == "Charlie"
        assert charlie.content_type == ContentType.SYSTEM

    def test_timestamps_are_parsed(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        # Timestamps should be increasing
        for i in range(1, len(messages)):
            assert messages[i].timestamp >= messages[i - 1].timestamp

    def test_message_ids_are_deterministic(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        msgs1 = collector.poll()
        msgs2 = collector.poll()
        assert [m.id for m in msgs1] == [m.id for m in msgs2]

    def test_message_ids_are_unique(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        messages = collector.poll()
        ids = [m.id for m in messages]
        assert len(ids) == len(set(ids))


# ── since_id filtering ───────────────────────────────────

class TestSinceIdFiltering:
    def test_since_id_filters_earlier_messages(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        all_msgs = collector.poll()
        # Get since_id from the 3rd message
        since = all_msgs[2].venue_message_id
        filtered = collector.poll(since_id=since)
        assert len(filtered) == len(all_msgs) - 3

    def test_since_id_none_returns_all(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        all_msgs = collector.poll(since_id=None)
        assert len(all_msgs) == 6

    def test_since_id_past_end_returns_empty(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        filtered = collector.poll(since_id="99999")
        assert filtered == []

    def test_since_id_zero_returns_all(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        all_msgs = collector.poll(since_id="0")
        assert len(all_msgs) == 6


# ── edge cases ───────────────────────────────────────────

class TestEdgeCases:
    def test_system_message_pinned(self, edge_case_transcript):
        collector = TranscriptFileCollector(path=edge_case_transcript)
        messages = collector.poll()
        assert messages[0].content_type == ContentType.SYSTEM
        assert messages[0].sender_name == "System"

    def test_sender_with_spaces(self, edge_case_transcript):
        collector = TranscriptFileCollector(path=edge_case_transcript)
        messages = collector.poll()
        assert messages[1].sender_name == "User With Spaces"
        assert messages[1].content == "message content here"

    def test_url_in_content(self, edge_case_transcript):
        collector = TranscriptFileCollector(path=edge_case_transcript)
        messages = collector.poll()
        assert "https://example.com" in messages[2].content

    def test_unicode_content(self, edge_case_transcript):
        collector = TranscriptFileCollector(path=edge_case_transcript)
        messages = collector.poll()
        unicode_msg = messages[3]
        assert "Héllo" in unicode_msg.content
        assert "🌍" in unicode_msg.content

    def test_empty_content(self, edge_case_transcript):
        collector = TranscriptFileCollector(path=edge_case_transcript)
        messages = collector.poll()
        # Empty message should still be parsed
        empty_msg = messages[4]
        assert empty_msg.sender_name == "Empty"

    def test_missing_file(self):
        collector = TranscriptFileCollector(path="/nonexistent/path.txt")
        messages = collector.poll()
        assert messages == []

    def test_empty_file(self, empty_transcript):
        collector = TranscriptFileCollector(path=empty_transcript)
        messages = collector.poll()
        assert messages == []

    def test_blank_lines_only(self, blank_transcript):
        collector = TranscriptFileCollector(path=blank_transcript)
        messages = collector.poll()
        assert messages == []


# ── agent mapping ────────────────────────────────────────

class TestAgentMapping:
    def test_agent_map_sets_agent_id(self, sample_transcript):
        collector = TranscriptFileCollector(
            path=sample_transcript,
            agent_map={"Alice": "agent_alice", "Bob": "agent_bob"},
        )
        messages = collector.poll()
        alice_msgs = [m for m in messages if m.sender_name == "Alice"]
        assert all(m.sender_agent_id == "agent_alice" for m in alice_msgs)

    def test_unmapped_sender_has_no_agent_id(self, sample_transcript):
        collector = TranscriptFileCollector(
            path=sample_transcript,
            agent_map={"Alice": "agent_alice"},
        )
        messages = collector.poll()
        bob_msgs = [m for m in messages if m.sender_name == "Bob"]
        assert all(m.sender_agent_id is None for m in bob_msgs)


# ── count_entries utility ────────────────────────────────

class TestCountEntries:
    def test_count_sample(self, sample_transcript):
        collector = TranscriptFileCollector(path=sample_transcript)
        assert collector.count_entries() == 6

    def test_count_missing_file(self):
        collector = TranscriptFileCollector(path="/nonexistent/path.txt")
        assert collector.count_entries() == 0

    def test_count_empty(self, empty_transcript):
        collector = TranscriptFileCollector(path=empty_transcript)
        assert collector.count_entries() == 0
