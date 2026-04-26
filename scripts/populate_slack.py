import sys
from pathlib import Path

# scripts/ is directly under repo root, so parents[1] = <repo root>
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.slack_service import _get_db, post_as_user  # noqa: E402


def run() -> None:
    db = _get_db()
    channels = {
        doc["channelId"]: doc.get("slackChannelId")
        for doc in db["slack_channels"].find({}, {"_id": 0, "channelId": 1, "slackChannelId": 1})
    }
    cursor = db["slack_messages"].find({}).sort("timestamp", 1)

    posted = 0
    failed = 0
    for message in cursor:
        channel_id = channels.get(message.get("channelId")) or message.get("channelId")
        try:
            post_as_user(
                user_id=message["userId"],
                text=message["text"],
                channel=channel_id,
            )
            posted += 1
            print(f"Posted {message.get('_id', '<no-id>')} -> {channel_id}")
        except Exception as exc:
            failed += 1
            print(f"Failed {message.get('_id', '<no-id>')}: {exc}")

    print(f"populateSlackService complete: posted={posted}, failed={failed}")


if __name__ == "__main__":
    run()
