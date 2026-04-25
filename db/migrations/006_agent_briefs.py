from datetime import UTC, datetime

from pymongo import UpdateOne

from ._seed_data import AGENT_BRIEFS


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    ops = []
    for brief in AGENT_BRIEFS:
        payload = dict(brief)
        payload["updatedAt"] = now
        ops.append(
            UpdateOne(
                {"briefId": brief["briefId"]},
                {"$set": payload, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        )
    result = db["agent_briefs"].bulk_write(ops)
    return result.upserted_count + result.modified_count
