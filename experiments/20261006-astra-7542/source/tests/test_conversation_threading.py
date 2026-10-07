"""Tests for conversation threading / ThreadAssembler."""
from __future__ import annotations

from conversation.threading import Thread, ThreadAssembler
from conversation.types import ContentType, Message, VenueType

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
    """Create a test message."""
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


# ── Thread dataclass ─────────────────────────────────────

class TestThread:
    def test_empty_thread(self):
        t = Thread(id="t1", venue="tg", venue_id="c1")
        assert t.message_count == 0
        assert t.duration_seconds == 0.0

    def test_add_message(self):
        t = Thread(id="t1", venue="tg", venue_id="c1")
        m = _msg(1, "Alice", "hello", BASE_TS)
        t.add_message(m)
        assert t.message_count == 1
        assert t.started_at == BASE_TS
        assert t.last_activity == BASE_TS
        assert "Alice" in t.participants

    def test_multiple_messages_track_time(self):
        t = Thread(id="t1", venue="tg", venue_id="c1")
        t.add_message(_msg(1, "Alice", "hi", BASE_TS))
        t.add_message(_msg(2, "Bob", "hey", BASE_TS + 60))
        t.add_message(_msg(3, "Alice", "how are you?", BASE_TS + 120))
        assert t.message_count == 3
        assert t.started_at == BASE_TS
        assert t.last_activity == BASE_TS + 120
        assert t.duration_seconds == 120.0
        assert t.participants == {"Alice", "Bob"}

    def test_agent_participants_tracked(self):
        t = Thread(id="t1", venue="tg", venue_id="c1")
        t.add_message(_msg(1, "Alice", "hi", BASE_TS, agent_id="agent_a"))
        t.add_message(_msg(2, "Bob", "hey", BASE_TS + 10))
        assert t.agent_participants == {"agent_a"}

    def test_sort_messages(self):
        t = Thread(id="t1", venue="tg", venue_id="c1")
        t.add_message(_msg(3, "C", "third", BASE_TS + 200))
        t.add_message(_msg(1, "A", "first", BASE_TS))
        t.add_message(_msg(2, "B", "second", BASE_TS + 100))
        t.sort_messages()
        assert [m.content for m in t.messages] == ["first", "second", "third"]
        assert t.started_at == BASE_TS
        assert t.last_activity == BASE_TS + 200


# ── ThreadAssembler: temporal grouping ───────────────────

class TestTemporalGrouping:
    def test_empty_input(self):
        ta = ThreadAssembler()
        assert ta.assemble([]) == []

    def test_single_message_thread(self):
        ta = ThreadAssembler(min_thread_messages=1)
        msgs = [_msg(1, "Alice", "hello", BASE_TS)]
        threads = ta.assemble(msgs)
        assert len(threads) == 1
        assert threads[0].message_count == 1

    def test_close_messages_grouped(self):
        ta = ThreadAssembler(gap_threshold_seconds=300, min_thread_messages=1)
        msgs = [
            _msg(1, "Alice", "hi", BASE_TS),
            _msg(2, "Bob", "hey", BASE_TS + 60),
            _msg(3, "Alice", "how are you?", BASE_TS + 120),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 1
        assert threads[0].message_count == 3

    def test_gap_splits_threads(self):
        ta = ThreadAssembler(gap_threshold_seconds=300, min_thread_messages=1)
        msgs = [
            _msg(1, "Alice", "topic 1", BASE_TS),
            _msg(2, "Bob", "topic 1 reply", BASE_TS + 60),
            # 10 minute gap
            _msg(3, "Alice", "topic 2", BASE_TS + 660),
            _msg(4, "Charlie", "topic 2 reply", BASE_TS + 700),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 2
        assert threads[0].message_count == 2
        assert threads[1].message_count == 2

    def test_threads_sorted_by_start_time(self):
        ta = ThreadAssembler(gap_threshold_seconds=60, min_thread_messages=1)
        msgs = [
            _msg(1, "A", "early", BASE_TS),
            _msg(2, "B", "later", BASE_TS + 120),
        ]
        threads = ta.assemble(msgs)
        assert threads[0].started_at < threads[1].started_at

    def test_different_venues_separate(self):
        ta = ThreadAssembler(gap_threshold_seconds=300, min_thread_messages=1)
        msgs = [
            _msg(1, "Alice", "chat1 msg", BASE_TS, venue_id="chat1"),
            _msg(2, "Alice", "chat2 msg", BASE_TS + 10, venue_id="chat2"),
            _msg(3, "Bob", "chat1 reply", BASE_TS + 20, venue_id="chat1"),
            _msg(4, "Bob", "chat2 reply", BASE_TS + 30, venue_id="chat2"),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 2
        venue_ids = {t.venue_id for t in threads}
        assert venue_ids == {"chat1", "chat2"}


# ── ThreadAssembler: reply chains ────────────────────────

class TestReplyChains:
    def test_simple_reply_chain(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=60,  # would split if no replies
            min_thread_messages=1,
        )
        msgs = [
            _msg(1, "Alice", "original", BASE_TS),
            _msg(2, "Bob", "reply to original", BASE_TS + 600, reply_to="1"),
        ]
        threads = ta.assemble(msgs)
        # Reply chain keeps them together despite gap
        assert len(threads) == 1
        assert threads[0].message_count == 2

    def test_deep_reply_chain(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=60,
            min_thread_messages=1,
        )
        msgs = [
            _msg(1, "A", "root", BASE_TS),
            _msg(2, "B", "reply1", BASE_TS + 600, reply_to="1"),
            _msg(3, "C", "reply2", BASE_TS + 1200, reply_to="2"),
            _msg(4, "A", "reply3", BASE_TS + 1800, reply_to="3"),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 1
        assert threads[0].message_count == 4

    def test_reply_chain_plus_temporal(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=300,
            min_thread_messages=1,
        )
        msgs = [
            _msg(1, "A", "thread 1 root", BASE_TS),
            _msg(2, "B", "thread 1 reply", BASE_TS + 600, reply_to="1"),
            # Separate temporal conversation
            _msg(3, "C", "unrelated", BASE_TS + 100),
            _msg(4, "D", "also unrelated", BASE_TS + 150),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 2


# ── ThreadAssembler: merging small threads ───────────────

class TestSmallThreadMerging:
    def test_single_messages_merged(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=60,
            min_thread_messages=3,
        )
        msgs = [
            _msg(1, "A", "msg1", BASE_TS),
            _msg(2, "B", "msg2", BASE_TS + 120),
            # Big enough group
            _msg(3, "A", "msg3", BASE_TS + 600),
            _msg(4, "B", "msg4", BASE_TS + 610),
            _msg(5, "C", "msg5", BASE_TS + 620),
        ]
        threads = ta.assemble(msgs)
        # The two small messages should be merged into the big group
        assert any(t.message_count >= 3 for t in threads)

    def test_all_small_merged_into_one(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=60,
            min_thread_messages=5,
        )
        msgs = [
            _msg(1, "A", "a", BASE_TS),
            _msg(2, "B", "b", BASE_TS + 120),
            _msg(3, "C", "c", BASE_TS + 240),
        ]
        threads = ta.assemble(msgs)
        # All small → merged into one
        assert len(threads) == 1
        assert threads[0].message_count == 3

    def test_min_thread_messages_one_no_merge(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=60,
            min_thread_messages=1,
        )
        msgs = [
            _msg(1, "A", "alone", BASE_TS),
            _msg(2, "B", "also alone", BASE_TS + 120),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 2


# ── ThreadAssembler: max thread size ─────────────────────

class TestMaxThreadSize:
    def test_max_thread_splits(self):
        ta = ThreadAssembler(
            gap_threshold_seconds=9999,
            min_thread_messages=1,
            max_thread_messages=5,
        )
        # 12 messages all close together
        msgs = [
            _msg(i, "User", f"msg{i}", BASE_TS + i * 10)
            for i in range(1, 13)
        ]
        threads = ta.assemble(msgs)
        assert len(threads) >= 2
        assert all(t.message_count <= 5 for t in threads)


# ── ThreadAssembler: mixed scenarios ─────────────────────

class TestMixedScenarios:
    def test_realistic_group_chat(self):
        """Simulate a realistic group chat with multiple topics and replies."""
        ta = ThreadAssembler(
            gap_threshold_seconds=300,
            min_thread_messages=2,
        )
        msgs = [
            # Morning discussion
            _msg(1, "Alice", "Good morning!", BASE_TS),
            _msg(2, "Bob", "Morning Alice!", BASE_TS + 30),
            _msg(3, "Charlie", "Hi everyone", BASE_TS + 45),
            # 10 minute break
            # Technical discussion
            _msg(4, "Alice", "Let's discuss the API design", BASE_TS + 700),
            _msg(5, "Bob", "Sure, I have some ideas", BASE_TS + 720),
            _msg(6, "Charlie", "Me too", BASE_TS + 740),
            _msg(7, "Alice", "What about REST vs GraphQL?", BASE_TS + 760),
            # Side reply to morning msg
            _msg(8, "Dave", "Sorry I'm late!", BASE_TS + 800, reply_to="1"),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) >= 2
        # All messages accounted for
        total = sum(t.message_count for t in threads)
        assert total == 8

    def test_unsorted_input(self):
        """Messages given out of order should still group correctly."""
        ta = ThreadAssembler(gap_threshold_seconds=300, min_thread_messages=1)
        msgs = [
            _msg(3, "C", "third", BASE_TS + 200),
            _msg(1, "A", "first", BASE_TS),
            _msg(2, "B", "second", BASE_TS + 100),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 1
        assert threads[0].messages[0].content == "first"
        assert threads[0].messages[-1].content == "third"

    def test_idempotent(self):
        """Running assemble twice gives same result."""
        ta = ThreadAssembler(gap_threshold_seconds=300, min_thread_messages=1)
        msgs = [
            _msg(1, "A", "hi", BASE_TS),
            _msg(2, "B", "hey", BASE_TS + 60),
        ]
        t1 = ta.assemble(msgs)
        t2 = ta.assemble(msgs)
        assert len(t1) == len(t2)
        assert t1[0].message_count == t2[0].message_count

    def test_participants_across_threads(self):
        """Same participant can appear in multiple threads."""
        ta = ThreadAssembler(gap_threshold_seconds=60, min_thread_messages=1)
        msgs = [
            _msg(1, "Alice", "morning", BASE_TS),
            _msg(2, "Alice", "afternoon", BASE_TS + 600),
        ]
        threads = ta.assemble(msgs)
        assert len(threads) == 2
        assert all("Alice" in t.participants for t in threads)
