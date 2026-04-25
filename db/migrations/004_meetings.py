from datetime import UTC, datetime

from pymongo import UpdateOne

from ._seed_data import MEETINGS


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    ops = []
    for meeting in MEETINGS:
        payload = dict(meeting)
        payload["updatedAt"] = now
        ops.append(
            UpdateOne(
                {"meetingId": meeting["meetingId"]},
                {"$set": payload, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        )
    result = db["meetings"].bulk_write(ops)
    return result.upserted_count + result.modified_count
