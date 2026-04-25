import json
import os
from pathlib import Path
from urllib import request

from dotenv import load_dotenv
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def postAsUser(userId: str, text: str, channelId: str | None = None) -> dict:
    """
    Write-only Slack post for Perform Action.
    Uses chat.postMessage with username/icon_emoji spoofing from Mongo users.
    """
    slack_token = os.getenv("SLACK_BOT_TOKEN", "")
    default_channel = os.getenv("SLACK_CHANNEL_ID", "")
    if not slack_token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set.")

    target_channel = channelId or default_channel
    if not target_channel:
        raise RuntimeError("channelId is required or SLACK_CHANNEL_ID must be set.")

    db = _get_db()
    user = db["users"].find_one({"_id": userId}, {"_id": 0, "slackDisplayName": 1, "avatarEmoji": 1})
    if not user:
        raise ValueError(f"User '{userId}' not found in users collection.")

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
