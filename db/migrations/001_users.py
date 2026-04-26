"""
Seeds the `standin.users` collection with StandIn team personas.

Adds `firstName` and `team` fields so that downstream consumers (orchestrator
name resolution, status filters, calendar attendee mapping) can do real
matching without hardcoding persona lists.

Also seeds a `standin_bot` row that `services/slack_service.py` reads when the
perform_action agent posts as the bot.
"""

from datetime import UTC, datetime


USERS = [
    {
        "_id": "user_alice",
        "name": "Alice Chen",
        "firstName": "Alice",
        "email": "alice@standin.ai",
        "slackDisplayName": "Alice Chen",
        "avatarEmoji": ":woman:",
        "role": "Product lead",
        "team": "Product",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_ben",
        "name": "Ben Okafor",
        "firstName": "Ben",
        "email": "ben@standin.ai",
        "slackDisplayName": "Ben Okafor",
        "avatarEmoji": ":male-technologist:",
        "role": "Engineering lead",
        "team": "Engineering",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_sara",
        "name": "Sara Malik",
        "firstName": "Sara",
        "email": "sara@standin.ai",
        "slackDisplayName": "Sara Malik",
        "avatarEmoji": ":briefcase:",
        "role": "Operations / business",
        "team": "Operations",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_james",
        "name": "James Wu",
        "firstName": "James",
        "email": "james@standin.ai",
        "slackDisplayName": "James Wu",
        "avatarEmoji": ":computer:",
        "role": "Frontend engineer",
        "team": "Engineering",
        "timezone": "America/Los_Angeles",
    },
    {
        "_id": "user_priya",
        "name": "Priya Nair",
        "firstName": "Priya",
        "email": "priya@standin.ai",
        "slackDisplayName": "Priya Nair",
        "avatarEmoji": ":microscope:",
        "role": "QA / reliability",
        "team": "QA",
        "timezone": "America/Los_Angeles",
    },
]


_STANDIN_BOT = {
    "_id": "standin_bot",
    "name": "StandIn Bot",
    "firstName": "StandIn",
    "email": "bot@standin.ai",
    "slackDisplayName": "StandIn",
    "avatarEmoji": ":robot_face:",
    "role": "Automation",
    "team": "StandIn",
    "timezone": "UTC",
}


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    db["users"].drop()
    docs = []
    for user in (*USERS, _STANDIN_BOT):
        payload = dict(user)
        payload["createdAt"] = now
        payload["updatedAt"] = now
        docs.append(payload)
    db["users"].insert_many(docs)
    return len(docs)
