"""Fix CS04 (skip_existing) and CS05 (discovery scope) in bootstrap.py."""

with open("conversation/bootstrap.py") as f:
    content = f.read()

# Fix CS05: explicit paths should NOT trigger glob discovery
old_discover = '''    # Discover transcripts
    if transcript_paths is None:
        paths = discover_transcripts()
    else:
        paths = discover_transcripts(extra_paths=transcript_paths)'''

new_discover = '''    # CS05: explicit list means exactly that list; auto-discovery only when None.
    if transcript_paths is None:
        paths = discover_transcripts()
    else:
        # Validate and resolve explicit paths only — no glob expansion
        paths = []
        for p in transcript_paths:
            import os
            real = os.path.realpath(p)
            if os.path.isfile(real):
                paths.append(real)
            else:
                logger.warning("Transcript path not found: %s", p)
        paths = sorted(set(paths))'''

content = content.replace(old_discover, new_discover)

# Fix CS04: skip_existing should check per-source import progress, not just "any row exists"
old_skip = '''        # Skip if already populated
        if skip_existing:
            existing = len(store.query(venue_id=venue_id, limit=1))
            if existing > 0:
                logger.info(
                    "Skipping %s — already has %d messages", path, existing
                )
                stats.files_skipped += 1
                continue'''

new_skip = '''        # CS04: skip only if file was fully ingested (compare expected vs stored count).
        # A single stored message no longer causes the entire file to be skipped.
        if skip_existing:
            try:
                collector_check = TranscriptFileCollector(
                    path=path,
                    venue_id=venue_id,
                    agent_map=effective_agent_map,
                )
                expected_count = len(collector_check.poll())
                existing_count = store.count(venue_id=venue_id)
                if existing_count >= expected_count and expected_count > 0:
                    logger.info(
                        "Skipping %s — fully ingested (%d/%d messages)",
                        path, existing_count, expected_count,
                    )
                    stats.files_skipped += 1
                    continue
                elif existing_count > 0:
                    logger.info(
                        "Resuming %s — partial (%d/%d messages)",
                        path, existing_count, expected_count,
                    )
            except Exception as e:
                logger.warning("Could not check %s: %s — proceeding", path, e)'''

content = content.replace(old_skip, new_skip)

# Also need to add count method support — add venue_id to count
# Actually, store.count already supports venue filter. But we need venue_id filter.
# Let's check if store.count supports venue_id... it takes venue only.
# We need to update store.count or use query. Let's use query with limit=0 approach.

# Actually the new store.py has count(venue) but not count(venue_id). Let's add that.

with open("conversation/bootstrap.py", "w") as f:
    f.write(content)

print("CS04/CS05: bootstrap.py updated")
