import json
import os
from pathlib import Path
from urllib import request

from dotenv import load_dotenv
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

# Migration 002 — #standin-updates (C005)
DEFAULT_SLACK_POST_CHANNEL_ID = "C0AVDKLBQF6"


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def resolve_slack_channel_for_post(db, channel: str | None) -> str:
    """
    Map optional channel key to a Slack chat.postMessage channel id.

    Empty / None -> SLACK_DEFAULT_CHANNEL_ID env or DEFAULT_SLACK_POST_CHANNEL_ID.
    Non-empty -> must match a row in slack_channels (slackChannelId, channelId, or name).
    """
    raw = (channel or "").strip()
    default = (os.getenv("SLACK_DEFAULT_CHANNEL_ID") or DEFAULT_SLACK_POST_CHANNEL_ID).strip()
    if not raw:
        return default or DEFAULT_SLACK_POST_CHANNEL_ID

    coll = db["slack_channels"]
    if coll.count_documents({}) == 0:
        raise ValueError(
            "slack_channels is empty — run migrations (002_slack_channels) before targeting "
            "a specific channel, or omit channel to use the default."
        )

    doc = coll.find_one({"slackChannelId": raw}, {"slackChannelId": 1})
    if doc:
        return doc["slackChannelId"]
    doc = coll.find_one({"channelId": raw}, {"slackChannelId": 1})
    if doc:
        return doc["slackChannelId"]
    doc = coll.find_one({"name": raw}, {"slackChannelId": 1})
    if doc:
        return doc["slackChannelId"]
    if not raw.startswith("#"):
        doc = coll.find_one({"name": f"#{raw}"}, {"slackChannelId": 1})
        if doc:
            return doc["slackChannelId"]

    allowed = list(coll.find({}, {"channelId": 1, "name": 1}).sort("channelId", 1))
    hint = ", ".join(f"{r['channelId']} ({r.get('name', '')})" for r in allowed) if allowed else "(none)"
    raise ValueError(
        f"Channel {raw!r} is not allowed. Use a channelId, name from slack_channels, or slackChannelId. "
        f"Allowed: {hint}"
    )


def postAsUser(user_id: str, text: str, channel: str | None = None) -> dict:
    """
    Write-only Slack post for Perform Action.
    Uses chat.postMessage with username/icon_emoji from Mongo users.
    channel is resolved via slack_channels (see resolve_slack_channel_for_post); omit for default.
    """
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    if not slack_token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set.")
    if not (text or "").strip():
        raise ValueError("Slack message text is required.")

    db = _get_db()
    target_channel = resolve_slack_channel_for_post(db, channel)

    user = db["users"].find_one({"_id": user_id}, {"_id": 0, "slackDisplayName": 1, "avatarEmoji": 1})
    if not user:
        raise ValueError(f"User '{user_id}' not found in users collection.")

    payload = {
        "channel": target_channel,
        "text": text,
        "username": user["slackDisplayName"],
        "icon_emoji": user["avatarEmoji"],
    }
    body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        SLACK_POST_MESSAGE_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {slack_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        raw = response.read().decode("utf-8")
    result = json.loads(raw)
    if not result.get("ok"):
        raise RuntimeError(f"Slack API error: {result.get('error', 'unknown_error')}")
    return result
