"""Fix CS13/CS10 in threading.py — applied against actual code structure."""

with open("conversation/threading.py") as f:
    content = f.read()

# Fix 1: CS10 — temporal grouping uses composite (venue, venue_id) key
content = content.replace(
    '        venue_groups: dict[str, list[Message]] = {}\n'
    '        for msg in unassigned:\n'
    '            venue_groups.setdefault(msg.venue_id, []).append(msg)',
    '        # CS10: composite key prevents cross-venue mixing\n'
    '        venue_groups: dict[tuple[str, str], list[Message]] = {}\n'
    '        for msg in unassigned:\n'
    '            venue_groups.setdefault((msg.venue, msg.venue_id), []).append(msg)',
)
content = content.replace(
    '        for _vid, msgs in venue_groups.items():',
    '        for (_venue, _vid), msgs in venue_groups.items():',
)

# Fix 2: CS13 — honor native thread_id in Phase 1
# Insert thread_id grouping before reply chain building
old_phase1 = '''        # Phase 1: Build reply chains
        reply_chains = self._build_reply_chains(sorted_msgs)

        # Phase 2: Group remaining by temporal proximity
        assigned_ids = set()
        for chain in reply_chains.values():
            for msg in chain:
                assigned_ids.add(msg.id)'''

new_phase1 = '''        # Phase 0: CS13 — group by native thread_id first
        native_threads: dict[str, list[Message]] = {}
        non_threaded: list[Message] = []
        for msg in sorted_msgs:
            if msg.thread_id:
                native_threads.setdefault(msg.thread_id, []).append(msg)
            else:
                non_threaded.append(msg)

        # Phase 1: Build reply chains from non-natively-threaded messages
        reply_chains = self._build_reply_chains(non_threaded)

        # Phase 2: Group remaining by temporal proximity
        assigned_ids: set[str] = set()
        # Mark native-threaded messages as assigned
        for chain in native_threads.values():
            for msg in chain:
                assigned_ids.add(msg.id)
        for chain in reply_chains.values():
            for msg in chain:
                assigned_ids.add(msg.id)'''

content = content.replace(old_phase1, new_phase1)

# Fix 3: Add native threads to Phase 3 thread building
old_phase3 = '''        # Phase 3: Build Thread objects
        threads: list[Thread] = []

        # From reply chains
        for root_id, chain_msgs in reply_chains.items():
            thread = self._make_thread(chain_msgs, thread_id_seed=root_id)
            threads.append(thread)'''

new_phase3 = '''        # Phase 3: Build Thread objects
        threads: list[Thread] = []

        # From native thread_ids (CS13)
        for tid, native_msgs in native_threads.items():
            thread = self._make_thread(native_msgs, thread_id_seed=tid)
            threads.append(thread)

        # From reply chains
        for root_id, chain_msgs in reply_chains.items():
            thread = self._make_thread(chain_msgs, thread_id_seed=root_id)
            threads.append(thread)'''

content = content.replace(old_phase3, new_phase3)

# Fix 4: CS13 — make find_root iterative (it's currently recursive)
old_find_root = '''        def find_root(msg_id: str, visited: set) -> str:
            if msg_id in visited:
                return msg_id  # cycle
            visited.add(msg_id)
            if msg_id in parent_of:
                return find_root(parent_of[msg_id], visited)
            return msg_id'''

new_find_root = '''        def find_root(msg_id: str, _visited: set = None) -> str:
            """CS13: iterative root-finding with cycle detection."""
            seen: set[str] = set()
            current = msg_id
            while current in parent_of:
                if current in seen:
                    return current  # cycle
                seen.add(current)
                current = parent_of[current]
            return current'''

content = content.replace(old_find_root, new_find_root)

# Fix 5: CS13 — enforce max_thread_messages in merge
# Add _split_oversized method and call it at end of _merge_small_threads
old_merge_return = '''        result: list[Thread] = []
        for _vid, vthreads in venue_threads.items():
            vthreads.sort(key=lambda t: t.started_at)
            merged = self._merge_small_in_venue(vthreads)
            result.extend(merged)

        return result'''

new_merge_return = '''        result: list[Thread] = []
        for _vid, vthreads in venue_threads.items():
            vthreads.sort(key=lambda t: t.started_at)
            merged = self._merge_small_in_venue(vthreads)
            result.extend(merged)

        # CS13: enforce max_thread_messages after all merges
        final: list[Thread] = []
        for t in result:
            if t.message_count > self.max_thread_messages:
                final.extend(self._split_oversized(t))
            else:
                final.append(t)
        return final

    def _split_oversized(self, thread: Thread) -> list[Thread]:
        """Split a thread that exceeds max_thread_messages into chunks."""
        thread.sort_messages()
        chunks: list[Thread] = []
        for i in range(0, len(thread.messages), self.max_thread_messages):
            batch = thread.messages[i : i + self.max_thread_messages]
            t = Thread(
                id=f"{thread.id}_p{i // self.max_thread_messages}",
                venue=thread.venue,
                venue_id=thread.venue_id,
            )
            for msg in batch:
                t.add_message(msg)
            chunks.append(t)
        return chunks'''

content = content.replace(old_merge_return, new_merge_return)

# Fix 6: CS10 — _merge_small_threads should key by composite (venue, venue_id)
content = content.replace(
    '        # Separate by venue_id\n'
    '        venue_threads: dict[str, list[Thread]] = {}\n'
    '        for t in threads:\n'
    '            venue_threads.setdefault(t.venue_id, []).append(t)',
    '        # CS10: separate by composite (venue, venue_id)\n'
    '        venue_threads: dict[tuple[str, str], list[Thread]] = {}\n'
    '        for t in threads:\n'
    '            venue_threads.setdefault((t.venue, t.venue_id), []).append(t)',
)

with open("conversation/threading.py", "w") as f:
    f.write(content)

print("CS13/CS10: threading.py updated")
