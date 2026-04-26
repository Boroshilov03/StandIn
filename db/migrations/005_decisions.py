from datetime import UTC, datetime

from pymongo import UpdateOne

from ._seed_data import DECISIONS


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    ops = []
    for decision in DECISIONS:
        payload = dict(decision)
        payload["updatedAt"] = now
        ops.append(
            UpdateOne(
                {"decisionId": decision["decisionId"]},
                {"$set": payload, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        )
    result = db["decisions"].bulk_write(ops)
    return result.upserted_count + result.modified_count
