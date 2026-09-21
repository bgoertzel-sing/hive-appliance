"""Fix CS08: Identity encoding collisions in types.py.

Change _message_id to use length-prefixed encoding instead of bare | delimiter.
Also add validation for Message fields.
"""

with open("conversation/types.py") as f:
    content = f.read()

# Replace _message_id with length-prefixed encoding
old_id = '''def _message_id(venue: str, venue_id: str, venue_message_id: str) -> str:
    """Deterministic message ID from venue coordinates."""
    raw = f"{venue}|{venue_id}|{venue_message_id}"
    return "msg_" + hashlib.sha256(raw.encode()).hexdigest()[:16]'''

new_id = '''def _message_id(venue: str, venue_id: str, venue_message_id: str) -> str:
    """Deterministic message ID from venue coordinates.

    Uses length-prefixed encoding to prevent delimiter collisions:
    e.g. ('a|b', 'c') vs ('a', 'b|c') produce different hashes.
    """
    parts = [venue, venue_id, venue_message_id]
    raw = ":".join(f"{len(p)}:{p}" for p in parts)
    return "msg_" + hashlib.sha256(raw.encode()).hexdigest()[:16]'''

content = content.replace(old_id, new_id)

# Add a validate() method to Message, after __post_init__
old_post_init = '''    def __post_init__(self):
        """Generate deterministic ID if not set."""
        if not self.id and self.venue and self.venue_id and self.venue_message_id:
            self.id = _message_id(self.venue, self.venue_id, self.venue_message_id)'''

new_post_init = '''    def __post_init__(self):
        """Generate deterministic ID if not set."""
        if not self.id and self.venue and self.venue_id and self.venue_message_id:
            self.id = _message_id(self.venue, self.venue_id, self.venue_message_id)

    def validate(self) -> list[str]:
        """Validate message fields. Returns list of error strings (empty = valid).

        Checks: non-empty ID, non-empty venue coordinates, finite timestamp,
        content is a string, metadata is serializable.
        """
        import math
        errors: list[str] = []
        if not self.id:
            errors.append("id is empty or unset")
        if not self.venue:
            errors.append("venue is empty")
        if not self.venue_id:
            errors.append("venue_id is empty")
        if not self.venue_message_id:
            errors.append("venue_message_id is empty")
        if not isinstance(self.timestamp, (int, float)):
            errors.append(f"timestamp is not numeric: {type(self.timestamp).__name__}")
        elif math.isnan(self.timestamp) or math.isinf(self.timestamp):
            errors.append(f"timestamp is not finite: {self.timestamp}")
        if not isinstance(self.content, str):
            errors.append(f"content is not a string: {type(self.content).__name__}")
        if not isinstance(self.sender_id, str):
            errors.append(f"sender_id is not a string: {type(self.sender_id).__name__}")
        # Validate metadata is JSON-serializable
        try:
            import json
            json.dumps(self.metadata)
        except (TypeError, ValueError) as e:
            errors.append(f"metadata is not JSON-serializable: {e}")
        return errors'''

content = content.replace(old_post_init, new_post_init)

with open("conversation/types.py", "w") as f:
    f.write(content)

print("CS08 + validation: types.py updated")
