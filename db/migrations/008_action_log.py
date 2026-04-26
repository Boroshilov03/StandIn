"""
Indexes for standin.action_log — audit trail written by perform_action.

Documents are inserted at runtime (no seed rows). This migration only
ensures the collection exists and has indexes for common retrieval patterns.
"""

from pymongo import ASCENDING, DESCENDING


def migrate(db) -> int:
    coll = db["action_log"]
    # Touch collection so it appears in Atlas even before first log write.
    # Sparse unique: only documents that include action_id participate (perform_action always sets it).
    coll.create_index(
        [("action_id", ASCENDING)],
        name="idx_action_id",
        unique=True,
        sparse=True,
    )
    coll.create_index(
        [("action_type", ASCENDING), ("created_at", DESCENDING)],
        name="idx_action_type_created_at",
    )
    coll.create_index([("created_at", DESCENDING)], name="idx_created_at")
    coll.create_index(
        [("action_type", ASCENDING), ("payload.user_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_action_type_user_created_at",
    )
    coll.create_index(
        [("action_type", ASCENDING), ("payload.event_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_action_type_event_created_at",
    )
    coll.create_index(
        [("action_type", ASCENDING), ("payload.calendar_event_id", ASCENDING), ("created_at", DESCENDING)],
        name="idx_action_type_calendar_event_created_at",
    )
    return 6
