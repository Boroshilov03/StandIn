from datetime import UTC, datetime


SLACK_CHANNELS = [
    {
        "channelId": "C001",
        "name": "#engineering-bugs",
        "slackChannelId": "C0AV3LHLYNP",
        "members": ["user_alice", "user_ben", "user_james", "user_priya"],
    },
    {
        "channelId": "C002",
        "name": "#operations",
        "slackChannelId": "C0AVA4AQ4N6",
        "members": ["user_alice", "user_sara"],
    },
    {
        "channelId": "C003",
        "name": "#product-roadmap",
        "slackChannelId": "C0AV80CFWT0",
        "members": ["user_alice", "user_ben", "user_priya"],
    },
    {
        "channelId": "C004",
        "name": "#project-discussions",
        "slackChannelId": "C0B091GN665",
        "members": ["user_alice", "user_ben", "user_james", "user_priya"],
    },
    {
        "channelId": "C005",
        "name": "#standin-updates",
        "slackChannelId": "C0AVDKLBQF6",
        "members": ["user_alice", "user_ben", "user_sara", "user_james", "user_priya"],
    },
]


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    db["slack_channels"].drop()
    docs = []
    for channel in SLACK_CHANNELS:
        payload = dict(channel)
        payload["createdAt"] = now
        payload["updatedAt"] = now
        docs.append(payload)
    db["slack_channels"].insert_many(docs)
    return len(docs)
