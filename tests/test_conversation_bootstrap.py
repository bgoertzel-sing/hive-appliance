"""Tests for conversation bootstrap — historical transcript ingestion."""
from __future__ import annotations

import os
import tempfile

import pytest

from conversation.types import Message, VenueType
from conversation.store import MessageStore
from conversation.semantic import SemanticIndex
from conversation.bootstrap import (
    BootstrapStats,
    discover_transcripts,
    bootstrap_from_transcripts,
    bootstrap_single_transcript,
    _venue_id_from_path,
)


# ── helpers ──────────────────────────────────────────────

SAMPLE_TRANSCRIPT = """\
[2026-09-18 10:00:00] Alice: Good morning everyone
[2026-09-18 10:00:30] Bob: Morning Alice!
[2026-09-18 10:01:00] Alice: Let's discuss the project
[2026-09-18 10:01:30] Bob: Sure, what's the status?
[2026-09-18 10:02:00] Alice: We're on track for the deadline
[2026-09-18 10:02:30] System: Bob joined the channel
[2026-09-18 10:03:00] Charlie: Hey everyone
[2026-09-18 10:03:30] Alice: Hi Charlie, welcome!
"""

SMALL_TRANSCRIPT = """\
[2026-09-18 12:00:00] Dave: Hello
[2026-09-18 12:00:30] Eve: Hi Dave
"""


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temp workspace with transcript files."""
    # Create agent directories with transcripts
    agent1_dir = tmp_path / "agent1"
    agent1_dir.mkdir()
    (agent1_dir / "transcript.txt").write_text(SAMPLE_TRANSCRIPT)

    agent2_dir = tmp_path / "agent2"
    agent2_dir.mkdir()
    (agent2_dir / "transcript.txt").write_text(SMALL_TRANSCRIPT)

    # Create store/index dirs
    db_path = str(tmp_path / "test.db")
    chroma_path = str(tmp_path / "chroma")
    os.makedirs(chroma_path, exist_ok=True)

    return tmp_path, db_path, chroma_path


# ── BootstrapStats ───────────────────────────────────────

class TestBootstrapStats:
    def test_default_stats(self):
        stats = BootstrapStats()
        assert stats.files_found == 0
        assert stats.messages_added == 0
        assert stats.errors == []

    def test_to_dict(self):
        stats = BootstrapStats(
            files_found=3,
            files_processed=2,
            files_failed=1,
            messages_parsed=100,
            messages_added=95,
            messages_indexed=95,
            duration_seconds=1.234,
            errors=["file3: parse error"],
        )
        d = stats.to_dict()
        assert d["files_found"] == 3
        assert d["messages_added"] == 95
        assert d["duration_seconds"] == 1.23
        assert len(d["errors"]) == 1


# ── discover_transcripts ────────────────────────────────

class TestDiscoverTranscripts:
    def test_discover_with_extra_paths(self, tmp_workspace):
        tmp_path, _, _ = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")
        paths = discover_transcripts(extra_paths=[t1])
        assert len(paths) >= 1
        assert any("agent1" in p for p in paths)

    def test_discover_nonexistent_path(self):
        paths = discover_transcripts(extra_paths=["/nonexistent/transcript.txt"])
        assert paths == []

    def test_discover_with_custom_globs(self, tmp_workspace):
        tmp_path, _, _ = tmp_workspace
        pattern = str(tmp_path / "*" / "transcript.txt")
        paths = discover_transcripts(globs=[pattern])
        assert len(paths) == 2

    def test_discover_deduplicates(self, tmp_workspace):
        tmp_path, _, _ = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")
        pattern = str(tmp_path / "*" / "transcript.txt")
        paths = discover_transcripts(extra_paths=[t1, t1], globs=[pattern])
        # No duplicates
        assert len(paths) == len(set(paths))


# ── _venue_id_from_path ─────────────────────────────────

class TestVenueIdFromPath:
    def test_simple_path(self):
        assert _venue_id_from_path("/hive/protomega2/transcript.txt") == "transcript_protomega2"

    def test_nested_path(self):
        result = _venue_id_from_path("/hive/gateway/iter-agents/agent1/transcript.txt")
        assert result == "transcript_agent1"


# ── bootstrap_from_transcripts ──────────────────────────

class TestBootstrapFromTranscripts:
    def test_bootstrap_basic(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        stats = bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_bootstrap",
        )
        assert stats.files_processed == 1
        assert stats.messages_parsed > 0
        assert stats.messages_added > 0
        assert stats.duration_seconds > 0
        assert stats.errors == []

    def test_bootstrap_multiple_files(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")
        t2 = str(tmp_path / "agent2" / "transcript.txt")

        stats = bootstrap_from_transcripts(
            transcript_paths=[t1, t2],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_bootstrap2",
        )
        assert stats.files_processed == 2
        assert stats.messages_parsed >= 10  # 8 + 2

    def test_bootstrap_skip_existing(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        # First run
        stats1 = bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_skip",
            skip_existing=True,
        )
        assert stats1.files_processed == 1

        # Second run — should skip
        stats2 = bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_skip",
            skip_existing=True,
        )
        assert stats2.files_skipped == 1
        assert stats2.files_processed == 0

    def test_bootstrap_no_skip(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        # First run
        bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_noskip",
            skip_existing=False,
        )

        # Second run — should NOT skip (dedup handled by store)
        stats2 = bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_noskip",
            skip_existing=False,
        )
        assert stats2.files_processed == 1
        # But no new messages added (dedup)
        assert stats2.messages_added == 0

    def test_bootstrap_empty_paths(self, tmp_workspace):
        _, db_path, chroma_path = tmp_workspace
        stats = bootstrap_from_transcripts(
            transcript_paths=[],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_empty",
        )
        assert stats.files_found == 0
        assert stats.files_processed == 0

    def test_bootstrap_with_agent_map(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        stats = bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_agentmap",
            agent_map={"Alice": "agent_alice", "Bob": "agent_bob"},
        )
        assert stats.files_processed == 1

        # Verify agent_ids were applied
        store = MessageStore(db_path)
        msgs = store.query(venue_id=_venue_id_from_path(t1))
        alice_msgs = [m for m in msgs if m.sender_id == "Alice"]
        assert len(alice_msgs) > 0
        assert all(m.sender_agent_id == "agent_alice" for m in alice_msgs)

    def test_bootstrap_stats_dict(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        stats = bootstrap_from_transcripts(
            transcript_paths=[t1],
            db_path=db_path,
            chroma_path=chroma_path,
            collection_name="test_dict",
        )
        d = stats.to_dict()
        assert isinstance(d, dict)
        assert "messages_added" in d
        assert "duration_seconds" in d


# ── bootstrap_single_transcript ─────────────────────────

class TestBootstrapSingleTranscript:
    def test_single_basic(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        store = MessageStore(db_path)
        index = SemanticIndex(
            persist_directory=chroma_path,
            collection_name="test_single",
        )

        added, indexed = bootstrap_single_transcript(
            path=t1,
            store=store,
            index=index,
        )
        assert added > 0
        assert indexed > 0

    def test_single_custom_venue_id(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace
        t1 = str(tmp_path / "agent1" / "transcript.txt")

        store = MessageStore(db_path)
        index = SemanticIndex(
            persist_directory=chroma_path,
            collection_name="test_single_venue",
        )

        added, indexed = bootstrap_single_transcript(
            path=t1,
            venue_id="custom_venue",
            store=store,
            index=index,
        )
        assert added > 0

        # Verify venue_id
        msgs = store.query(venue_id="custom_venue")
        assert len(msgs) > 0

    def test_single_empty_file(self, tmp_workspace):
        tmp_path, db_path, chroma_path = tmp_workspace

        empty_dir = tmp_path / "empty_agent"
        empty_dir.mkdir()
        empty_file = empty_dir / "transcript.txt"
        empty_file.write_text("")

        store = MessageStore(db_path)
        index = SemanticIndex(
            persist_directory=chroma_path,
            collection_name="test_single_empty",
        )

        added, indexed = bootstrap_single_transcript(
            path=str(empty_file),
            store=store,
            index=index,
        )
        assert added == 0
        assert indexed == 0
