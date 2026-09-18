# Design: Hive Conversation Store

**Author:** ProtoMegaBot2  
**Date:** 2026-09-18  
**Status:** DRAFT — awaiting feedback  
**Predecessor:** M5 Hive-Level Appliance (complete)

---

## 1. Motivation

The hive hosts multiple agents (ProtoMegaBot2, ProtoCosmo2, ProtoCosmoPopos,
etc.) that communicate across many venues: Telegram groups, Telegram 1-on-1,
Slack channels, and potentially others. Each agent currently has its own
transcript/episode history but no shared, queryable archive of cross-agent
conversations.

A **Hive Conversation Store** would provide:

- **Cross-conversation awareness** — any agent can query what was discussed
  in other venues/threads, enabling coherent multi-venue coordination.
- **Historical record** — persistent, append-only archive of all agent
  communications for audit, replay, and learning.
- **Semantic search** — full-text and embedding-based retrieval across the
  entire conversation corpus.
- **Shared context** — agents can reference conversations they weren't
  party to, reducing repeated explanations and lost context.

## 2. Why Separate from the Hive Appliance

The Appliance (M0–M5) handles **infrastructure health**: observations,
incidents, repair plans, and cross-agent operational coordination. The
Conversation Store handles **communication content**: messages, threads,
semantic meaning, and cross-venue awareness.

| Dimension          | Hive Appliance          | Conversation Store        |
|--------------------|-------------------------|---------------------------|
| Concern            | Infra health & repair   | Agent communication       |
| Event lifetime     | Operational (trimmable) | Permanent (append-only)   |
| Storage profile    | Bounded event logs      | Continuous growth         |
| Query pattern      | Time-range, kind, sev.  | Full-text, semantic, thread|
| Consumers          | Hive-wide ops           | Per-agent reasoning       |
| Ownership          | Shared infrastructure   | Shared knowledge          |

The Appliance can optionally **observe** the Conversation Store as a data
source (e.g., detect communication failures, monitor message rates).

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              Hive Conversation Store                 │
│                                                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ Venue    │  │  Message   │  │  Query Engine    │ │
│  │Collectors│→ │   Store    │→ │ (text+semantic)  │ │
│  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘ │
│       │              │                  │           │
│  ┌────┴─────┐  ┌─────┴─────┐  ┌────────┴─────────┐│
│  │Thread    │  │  Index    │  │   Agent Query    ││
│  │Assembler │  │ Manager   │  │     API          ││
│  └──────────┘  └───────────┘  └──────────────────┘│
└─────────────────────────────────────────────────────┘
        ↑               ↑               ↓
   ┌────┴────┐    ┌─────┴────┐    ┌─────┴──────┐
   │Telegram │    │  Slack   │    │  Agent     │
   │ Groups  │    │ Channels │    │  Queries   │
   │ & 1-on-1│    │          │    │            │
   └─────────┘    └──────────┘    └────────────┘
```

## 4. Core Components

### 4.1 Message Record

The fundamental unit is a `Message` — a single utterance in a conversation:

```python
@dataclass
class Message:
    id: str                    # Deterministic: venue + venue_message_id
    venue: str                 # "telegram_group", "telegram_dm", "slack"
    venue_id: str              # Chat/channel ID within the venue
    venue_message_id: str      # Platform-native message ID
    thread_id: str | None      # Thread/reply-chain ID if applicable
    sender_id: str             # Platform user ID
    sender_name: str           # Display name at time of message
    sender_agent_id: str | None # Hive agent_id if sender is an agent
    timestamp: float           # UTC epoch seconds
    content: str               # Raw text content
    content_type: str          # "text", "voice_transcript", "media_caption"
    reply_to_id: str | None    # ID of message this replies to
    metadata: dict             # Platform-specific extras
    schema_version: str = "1"
```

### 4.2 Venue Collectors

Each venue type has a collector that transforms platform-native messages
into `Message` records:

```python
class VenueCollector(Protocol):
    """Collects messages from a specific venue."""

    @property
    def venue_type(self) -> str: ...

    @property
    def venue_id(self) -> str: ...

    def poll(self, since_id: str | None = None) -> list[Message]:
        """Fetch new messages since the last known ID."""
        ...
```

**Planned collectors:**
- `TelegramGroupCollector` — polls group chat history
- `TelegramDMCollector` — polls 1-on-1 conversations
- `SlackChannelCollector` — polls Slack channel history
- `TranscriptFileCollector` — ingests existing transcript.txt files
  (bootstrap: import each agent's historical transcripts)

### 4.3 Message Store

Append-only, durable storage for all messages:

```python
class MessageStore(Protocol):
    """Persistent, append-only message storage."""

    def append(self, messages: list[Message]) -> int:
        """Append messages, dedup by ID. Returns count added."""
        ...

    def get(self, message_id: str) -> Message | None: ...

    def query(
        self,
        venue: str | None = None,
        venue_id: str | None = None,
        sender_agent_id: str | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[Message]: ...

    def count(self) -> int: ...
```

**Initial backend:** SQLite (single file, WAL mode, full-text search via
FTS5). Path: `/hive/shared/conversation-store/messages.db`

**Growth estimate:** ~10K messages/day across all venues × ~500 bytes avg
= ~5 MB/day = ~1.8 GB/year. Well within SQLite's comfort zone for years.

### 4.4 Semantic Index

Embedding-based retrieval for "find conversations about X":

```python
class SemanticIndex(Protocol):
    """Vector similarity search over message content."""

    def index(self, messages: list[Message]) -> None:
        """Add messages to the semantic index."""
        ...

    def search(
        self,
        query: str,
        k: int = 10,
        venue: str | None = None,
        since: float | None = None,
    ) -> list[tuple[Message, float]]:
        """Find semantically similar messages. Returns (message, distance)."""
        ...
```

**Initial backend:** ChromaDB (already available in the hive environment).
Collection: `hive_conversations`. Embeddings via the same provider used
for agent LTM.

### 4.5 Thread Assembler

Groups messages into conversational threads for coherent retrieval:

```python
@dataclass
class Thread:
    id: str                    # Deterministic from first message
    venue: str
    venue_id: str
    messages: list[Message]    # Ordered by timestamp
    participants: set[str]     # sender_ids
    agent_participants: set[str]  # agent_ids
    started_at: float
    last_activity: float
    topic_summary: str | None  # LLM-generated summary (lazy)
```

Threading strategy:
- Telegram: `reply_to_message_id` chains + temporal proximity heuristic
- Slack: native thread_ts
- Fallback: sliding window with speaker-change detection

### 4.6 Agent Query API

The interface agents use to query the store:

```python
class ConversationStoreClient:
    """Client API for agents to query the Conversation Store."""

    def search(self, query: str, k: int = 10, **filters) -> list[Thread]: ...
    def recent(self, venue: str | None, hours: int = 24) -> list[Thread]: ...
    def by_participant(self, agent_id: str, limit: int = 50) -> list[Thread]: ...
    def context_for(self, message_id: str, window: int = 20) -> list[Message]: ...
    def summary(self, venue_id: str, since: float) -> str: ...
```

## 5. Data Flow

```
1. VenueCollectors poll their venues on a schedule (e.g., every 60s)
2. New Messages are appended to the MessageStore (deduped by ID)
3. New Messages are indexed in the SemanticIndex
4. ThreadAssembler groups messages into Threads (on-demand or periodic)
5. Agents query via ConversationStoreClient (text search, semantic, or browse)
6. (Optional) HiveAppliance observes store health metrics as events
```

## 6. Bootstrap Strategy

To provide immediate value, the store should ingest existing data:

1. **Transcript files** — each agent has `transcript.txt` with historical
   messages. A `TranscriptFileCollector` parses these into Messages.
2. **Episode history** — agents' episodic memory contains timestamped
   conversation fragments. These can supplement transcript gaps.
3. **Forward collection** — once collectors are running, new messages
   flow automatically.

## 7. Integration with Hive Appliance

The Conversation Store is a **peer service**, not a child of the Appliance:

- The Appliance can register a `ConversationStoreAdapter` that exposes
  store health metrics (message rate, index lag, storage usage) as events.
- The Appliance planner could trigger store maintenance (reindex, compact)
  as repair actions.
- Agents use the store independently of the Appliance for reasoning.

## 8. Privacy & Access Control

- All messages are already visible to agents in their respective venues.
  The store consolidates but does not expand access.
- Per-venue access policies can restrict which agents query which venues.
- DM conversations may be excluded or access-controlled by default.
- No external API — store is hive-internal only.

## 9. Implementation Plan

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| P1    | Core store | Message, MessageStore (SQLite), basic query API |
| P2    | Semantic search | SemanticIndex (ChromaDB), embedding pipeline |
| P3    | Collectors | TelegramGroupCollector, TranscriptFileCollector |
| P4    | Threading | ThreadAssembler, topic summaries |
| P5    | Integration | HiveAppliance adapter, agent client library |
| P6    | Bootstrap | Ingest historical transcripts, backfill index |

## 10. Open Questions

1. **Storage location:** `/hive/shared/` vs. per-agent with federation?
   Recommendation: shared, since the whole point is cross-agent access.
2. **Embedding model:** reuse each agent's existing embeddings provider,
   or standardize on one model for the shared index?
3. **Real-time vs. polling:** start with polling; consider webhook/push
   integration for lower latency if needed.
4. **Message retention:** keep everything forever, or age-based tiers
   (hot: SQLite+vectors, cold: compressed archives)?
5. **DM privacy:** include agent-to-human DMs in the shared store, or
   keep those private per-agent?

---

*This document is a design proposal. Implementation awaits feedback and
prioritization confirmation.*
