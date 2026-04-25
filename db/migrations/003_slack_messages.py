from datetime import UTC, datetime

from pymongo import UpdateOne

from ._seed_data import SLACK_MESSAGES


def _message_key(message: dict) -> str:
    return f"{message['channelId']}:{message['timestamp']}:{message['userId']}"


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    ops = []
    for message in SLACK_MESSAGES:
        payload = dict(message)
        payload["messageKey"] = _message_key(message)
        payload["updatedAt"] = now
        ops.append(
            UpdateOne(
                {"messageKey": payload["messageKey"]},
                {"$set": payload, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        )
    result = db["slack_messages"].bulk_write(ops)
    return result.upserted_count + result.modified_count
