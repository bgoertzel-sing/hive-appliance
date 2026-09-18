"""ThreadAssembler — groups messages into conversational threads.

Threading strategies:
1. Explicit reply chains: follow reply_to_id links
2. Temporal proximity: group messages within a time window when no
   explicit threading is available
3. Speaker-change heuristic: detect topic shifts based on participant
   patterns and temporal gaps

The assembler works on-demand over a list of messages (typically from
a MessageStore query), not as a persistent service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from conversation.types import Message


# ── Thread dataclass ─────────────────────────────────────

@dataclass
class Thread:
    """A conversational thread — a coherent sequence of related messages.

    Attributes
    ----------
    id:
        Deterministic identifier derived from the first message's id.
    venue:
        Venue type (e.g. 'telegram_group').
    venue_id:
        Venue-specific chat/channel identifier.
    messages:
        Messages in chronological order.
    participants:
        Set of sender_ids involved.
    agent_participants:
        Set of agent_ids involved (subset of participants that are agents).
    started_at:
        Timestamp of the first message.
    last_activity:
        Timestamp of the last message.
    topic_summary:
        Optional LLM-generated summary (populated lazily).
    """
    id: str
    venue: str
    venue_id: str
    messages: list[Message] = field(default_factory=list)
    participants: set[str] = field(default_factory=set)
    agent_participants: set[str] = field(default_factory=set)
    started_at: float = 0.0
    last_activity: float = 0.0
    topic_summary: Optional[str] = None

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def duration_seconds(self) -> float:
        if not self.messages:
            return 0.0
        return self.last_activity - self.started_at

    def add_message(self, msg: Message) -> None:
        """Add a message and update thread metadata."""
        self.messages.append(msg)
        self.participants.add(msg.sender_id)
        if msg.sender_agent_id:
            self.agent_participants.add(msg.sender_agent_id)
        if not self.started_at or msg.timestamp < self.started_at:
            self.started_at = msg.timestamp
        if msg.timestamp > self.last_activity:
            self.last_activity = msg.timestamp

    def sort_messages(self) -> None:
        """Sort messages by timestamp."""
        self.messages.sort(key=lambda m: m.timestamp)
        if self.messages:
            self.started_at = self.messages[0].timestamp
            self.last_activity = self.messages[-1].timestamp


# ── ThreadAssembler ──────────────────────────────────────

@dataclass
class ThreadAssembler:
    """Groups messages into conversational threads.

    Parameters
    ----------
    gap_threshold_seconds:
        Maximum time gap between consecutive messages in the same
        thread when using temporal proximity grouping. Default: 300s (5 min).
    min_thread_messages:
        Minimum number of messages to form a thread. Shorter sequences
        are merged into the nearest adjacent thread. Default: 2.
    max_thread_messages:
        Maximum messages in a single thread before forcing a split.
        Default: 200.
    """
    gap_threshold_seconds: float = 300.0
    min_thread_messages: int = 2
    max_thread_messages: int = 200

    def assemble(self, messages: list[Message]) -> list[Thread]:
        """Group messages into threads.

        Uses a hybrid strategy:
        1. First, build explicit reply chains from reply_to_id links.
        2. Then, group remaining messages by temporal proximity within
           the same venue_id.
        3. Merge undersized threads into neighbors.

        Parameters
        ----------
        messages:
            Messages to group, in any order.

        Returns
        -------
        list[Thread]
            Threads sorted by start time.
        """
        if not messages:
            return []

        # Sort by timestamp
        sorted_msgs = sorted(messages, key=lambda m: m.timestamp)

        # Phase 1: Build reply chains
        reply_chains = self._build_reply_chains(sorted_msgs)

        # Phase 2: Group remaining by temporal proximity
        assigned_ids = set()
        for chain in reply_chains.values():
            for msg in chain:
                assigned_ids.add(msg.id)

        unassigned = [m for m in sorted_msgs if m.id not in assigned_ids]

        # Group unassigned by venue_id, then by temporal gap
        venue_groups: dict[str, list[Message]] = {}
        for msg in unassigned:
            venue_groups.setdefault(msg.venue_id, []).append(msg)

        temporal_threads: list[list[Message]] = []
        for vid, msgs in venue_groups.items():
            temporal_threads.extend(self._split_by_gap(msgs))

        # Phase 3: Build Thread objects
        threads: list[Thread] = []

        # From reply chains
        for root_id, chain_msgs in reply_chains.items():
            thread = self._make_thread(chain_msgs, thread_id_seed=root_id)
            threads.append(thread)

        # From temporal groups
        for group in temporal_threads:
            if group:
                thread = self._make_thread(group, thread_id_seed=group[0].id)
                threads.append(thread)

        # Phase 4: Merge undersized threads
        threads = self._merge_small_threads(threads)

        # Sort threads by start time
        threads.sort(key=lambda t: t.started_at)

        return threads

    # ── reply chain builder ──────────────────────────────

    def _build_reply_chains(
        self, messages: list[Message]
    ) -> dict[str, list[Message]]:
        """Build reply chains from reply_to_id links.

        Returns a dict mapping root message ID → list of messages in chain.
        Only creates chains with >= 2 messages.
        """
        msg_by_id: dict[str, Message] = {m.id: m for m in messages}
        msg_by_venue_id: dict[str, Message] = {}
        for m in messages:
            key = f"{m.venue_id}:{m.venue_message_id}"
            msg_by_venue_id[key] = m

        # Build parent mapping
        parent_of: dict[str, str] = {}
        for msg in messages:
            if msg.reply_to_id:
                # reply_to_id might be a venue_message_id or a full id
                parent_key = f"{msg.venue_id}:{msg.reply_to_id}"
                if parent_key in msg_by_venue_id:
                    parent_of[msg.id] = msg_by_venue_id[parent_key].id
                elif msg.reply_to_id in msg_by_id:
                    parent_of[msg.id] = msg.reply_to_id

        # Find roots
        def find_root(msg_id: str, visited: set) -> str:
            if msg_id in visited:
                return msg_id  # cycle
            visited.add(msg_id)
            if msg_id in parent_of:
                return find_root(parent_of[msg_id], visited)
            return msg_id

        # Group by root
        chains: dict[str, list[Message]] = {}
        for msg in messages:
            if msg.id in parent_of or msg.id in {
                parent_of.get(m.id) for m in messages if m.id in parent_of
            }:
                root = find_root(msg.id, set())
                chains.setdefault(root, []).append(msg)

        # Remove chains with only 1 message (they'll be handled temporally)
        return {k: v for k, v in chains.items() if len(v) >= 2}

    # ── temporal grouping ────────────────────────────────

    def _split_by_gap(self, messages: list[Message]) -> list[list[Message]]:
        """Split a chronological list of messages by temporal gaps."""
        if not messages:
            return []

        groups: list[list[Message]] = [[messages[0]]]

        for msg in messages[1:]:
            # Check if current group is full
            if len(groups[-1]) >= self.max_thread_messages:
                groups.append([msg])
                continue

            gap = msg.timestamp - groups[-1][-1].timestamp
            if gap > self.gap_threshold_seconds:
                groups.append([msg])
            else:
                groups[-1].append(msg)

        return groups

    # ── thread construction ──────────────────────────────

    def _make_thread(
        self, messages: list[Message], thread_id_seed: str
    ) -> Thread:
        """Create a Thread from a list of messages."""
        thread = Thread(
            id=f"thread_{thread_id_seed}",
            venue=messages[0].venue if messages else "",
            venue_id=messages[0].venue_id if messages else "",
        )
        for msg in sorted(messages, key=lambda m: m.timestamp):
            thread.add_message(msg)
        return thread

    # ── merging ──────────────────────────────────────────

    def _merge_small_threads(self, threads: list[Thread]) -> list[Thread]:
        """Merge threads with fewer than min_thread_messages into neighbors.

        Small threads are merged into the nearest thread (by time) in the
        same venue_id.
        """
        if not threads or self.min_thread_messages <= 1:
            return threads

        # Separate by venue_id
        venue_threads: dict[str, list[Thread]] = {}
        for t in threads:
            venue_threads.setdefault(t.venue_id, []).append(t)

        result: list[Thread] = []
        for vid, vthreads in venue_threads.items():
            vthreads.sort(key=lambda t: t.started_at)
            merged = self._merge_small_in_venue(vthreads)
            result.extend(merged)

        return result

    def _merge_small_in_venue(self, threads: list[Thread]) -> list[Thread]:
        """Merge small threads within a single venue."""
        if len(threads) <= 1:
            return threads

        # Mark small threads for merging
        keep: list[Thread] = []
        small: list[Thread] = []

        for t in threads:
            if t.message_count < self.min_thread_messages:
                small.append(t)
            else:
                keep.append(t)

        if not keep:
            # All threads are small — merge everything into one
            merged = Thread(
                id=threads[0].id,
                venue=threads[0].venue,
                venue_id=threads[0].venue_id,
            )
            for t in threads:
                for msg in t.messages:
                    merged.add_message(msg)
            merged.sort_messages()
            return [merged]

        # Merge each small thread into the nearest kept thread
        for small_t in small:
            nearest = min(
                keep,
                key=lambda k: abs(k.last_activity - small_t.started_at),
            )
            for msg in small_t.messages:
                nearest.add_message(msg)
            nearest.sort_messages()

        return keep
