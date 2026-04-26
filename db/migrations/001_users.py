from datetime import UTC, datetime


USERS = [
    {
        "_id": "user_alice",
        "name": "Alice Chen",
        "email": "alice@standin.ai",
        "slackDisplayName": "Alice Chen",
        "avatarEmoji": ":grinning_cat:",
        "role": "Product lead",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_ben",
        "name": "Ben Okafor",
        "email": "ben@standin.ai",
        "slackDisplayName": "Ben Okafor",
        "avatarEmoji": ":male-technologist:",
        "role": "Engineering lead",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_sara",
        "name": "Sara Malik",
        "email": "sara@standin.ai",
        "slackDisplayName": "Sara Malik",
        "avatarEmoji": ":briefcase:",
        "role": "Operations / business",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_james",
        "name": "James Wu",
        "email": "james@standin.ai",
        "slackDisplayName": "James Wu",
        "avatarEmoji": ":computer:",
        "role": "Frontend engineer",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_priya",
        "name": "Priya Nair",
        "email": "priya@standin.ai",
        "slackDisplayName": "Priya Nair",
        "avatarEmoji": ":microscope:",
        "role": "QA / reliability",
        "timezone": "America/Los_Angeles",
    },
]


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    db["users"].drop()
    docs = []
    for user in USERS:
        payload = dict(user)
        payload["createdAt"] = now
        payload["updatedAt"] = now
        docs.append(payload)
    db["users"].insert_many(docs)
    return len(docs)
