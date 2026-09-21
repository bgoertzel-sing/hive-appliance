"""Fix CS02/CS03/CS10/CS12 in client.py."""

with open("conversation/client.py") as f:
    content = f.read()

# Fix 1: _dict_to_message — CS02: preserve canonical ID from semantic results
old_dict_to_msg = '''def _dict_to_message(d: dict) -> Message:
    """Convert a SemanticIndex result dict back into a Message."""
    meta = d.get("metadata", {})
    return Message(
        venue=meta.get("venue", ""),
        venue_id=meta.get("venue_id", ""),
        venue_message_id=meta.get("venue_message_id", ""),
        sender_id=meta.get("sender_id", ""),
        sender_name=meta.get("sender_name", ""),
        sender_agent_id=meta.get("sender_agent_id") or None,
        timestamp=meta.get("timestamp", 0.0),
        content=d.get("content", ""),
        content_type=meta.get("content_type", "text"),
        reply_to_id=meta.get("reply_to_id") or None,
    )'''

new_dict_to_msg = '''def _dict_to_message(d: dict) -> Message:
    """Convert a SemanticIndex result dict back into a Message.

    Preserves the canonical message ID from the index (which is the same
    deterministic ID used in MessageStore). Restores all venue coordinates
    and provenance from stored metadata.
    """
    meta = d.get("metadata", {})
    return Message(
        id=d.get("id", ""),  # CS02: preserve canonical ID
        venue=meta.get("venue", ""),
        venue_id=meta.get("venue_id", ""),
        venue_message_id=meta.get("venue_message_id", ""),
        sender_id=meta.get("sender_id", ""),
        sender_name=meta.get("sender_name", ""),
        sender_agent_id=meta.get("sender_agent_id") or None,
        timestamp=meta.get("timestamp", 0.0),
        content=d.get("content", ""),
        content_type=meta.get("content_type", "text"),
        thread_id=meta.get("thread_id") or None,
        reply_to_id=meta.get("reply_to_id") or None,
    )'''

content = content.replace(old_dict_to_msg, new_dict_to_msg)

# Fix 2: CS03 — ingest should only index what was actually accepted by SQL
old_ingest = '''    def ingest(self, messages: list[Message]) -> int:
        """Ingest messages into both store and index.

        This is the primary write path: messages go into SQLite first
        (source of truth with dedup), then into the semantic index.

        Returns count actually added to the store.
        """
        if not messages:
            return 0

        added = self.store.append(messages)

        # Index all supplied messages (upsert is idempotent in Chroma)
        indexable = [m for m in messages if m.content.strip()]
        if indexable:
            self.index.add(indexable)

        return added'''

new_ingest = '''    def ingest(self, messages: list[Message]) -> int:
        """Ingest messages into both store and index.

        This is the primary write path: messages go into SQLite first
        (source of truth with dedup), then only accepted records are indexed.
        CS03: only index what the canonical store accepted, not raw input.

        Returns count actually added to the store.
        """
        if not messages:
            return 0

        added = self.store.append(messages)

        # CS03: only index messages that were actually accepted (new inserts).
        # Query the store to get canonical records for each ID and index those.
        if added > 0:
            accepted: list[Message] = []
            for msg in messages:
                if msg.id and msg.content.strip():
                    canonical = self.store.get_by_id(msg.id)
                    if canonical is not None:
                        accepted.append(canonical)
            if accepted:
                self.index.add(accepted)

        return added'''

content = content.replace(old_ingest, new_ingest)

# Fix 3: CS10 — search/context methods should scope by venue composite key
# The search method's semantic results need venue-scoped thread assembly
old_search_method = '''        # SemanticIndex.search supports: query, k, venue, venue_id,
        # sender_agent_id, since — but NOT until.
        # We apply 'until' as a post-filter.
        results = self.index.search(
            query=query,
            k=k,
            venue=venue,
            venue_id=venue_id,
            since=since,
        )

        # Convert dicts → (Message, distance) pairs
        pairs: list[tuple[Message, float]] = []
        for d in results:
            msg = _dict_to_message(d)
            dist = d.get("distance", 0.0)

            # Apply post-filters
            if until and msg.timestamp > until:
                continue

            pairs.append((msg, dist))'''

new_search_method = '''        # SemanticIndex.search supports: query, k, venue, venue_id,
        # sender_agent_id, since — but NOT until.
        # CS12: pass venue filters to Chroma for pushed-down filtering.
        # We apply 'until' as a post-filter, over-fetching to compensate.
        overfetch = k * 3 if until else k
        results = self.index.search(
            query=query,
            k=overfetch,
            venue=venue,
            venue_id=venue_id,
            since=since,
        )

        # CS02: hydrate canonical records from store when available
        pairs: list[tuple[Message, float]] = []
        for d in results:
            dist = d.get("distance", 0.0)
            canonical_id = d.get("id", "")
            # Try to hydrate from store for full identity
            canonical = self.store.get_by_id(canonical_id) if canonical_id else None
            msg = canonical if canonical is not None else _dict_to_message(d)

            # Apply post-filters
            if until and msg.timestamp > until:
                continue

            pairs.append((msg, dist))
            if len(pairs) >= k:
                break'''

content = content.replace(old_search_method, new_search_method)

# Fix 4: CS10 — context_for should scope by venue
old_context_for = '''    def context_for(
        self,
        message_id: str,
        window: int = 10,
    ) -> list[Message]:
        """Get conversational context around a specific message.

        Returns surrounding messages from the same venue, ordered
        chronologically.

        Parameters
        ----------
        message_id:
            The canonical message ID.
        window:
            Number of messages to include before and after.
        """
        return self.store.context_around(
            message_id=message_id,
            before=window,
            after=window,
        )'''

new_context_for = '''    def context_for(
        self,
        message_id: str,
        window: int = 10,
    ) -> list[Message]:
        """Get conversational context around a specific message.

        Returns surrounding messages from the same venue, ordered
        chronologically. CS10: scopes to the target's (venue, venue_id)
        to prevent cross-venue leakage.

        Parameters
        ----------
        message_id:
            The canonical message ID.
        window:
            Number of messages to include before and after.
        """
        # CS10: first look up the target to get its venue scope
        target = self.store.get_by_id(message_id)
        if target is None:
            return []

        return self.store.context_around(
            message_id=message_id,
            before=window,
            after=window,
            venue=target.venue,
            venue_id=target.venue_id,
        )'''

content = content.replace(old_context_for, new_context_for)

with open("conversation/client.py", "w") as f:
    f.write(content)

print("CS02/CS03/CS10/CS12: client.py updated")
