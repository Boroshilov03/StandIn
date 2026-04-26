from datetime import UTC, datetime

from pymongo import UpdateOne

from ._seed_data import AGENT_BRIEFS, DECISIONS, MEETINGS, SLACK_MESSAGES, USERS


def _doc_from_user(user: dict) -> dict:
    return {
        "id": f"user_profile_{user['_id']}",
        "source": "migration_user",
        "filename": "users",
        "title": f"User profile — {user.get('name', user['_id'])}",
        "type": "user_profile",
        "role": "",
        "author": user["_id"],
        "timestamp": "",
        "tags": ["user", "profile"],
        "content": (
            f"Name: {user.get('name', '')}\n"
            f"Email: {user.get('email', '')}\n"
            f"Slack display name: {user.get('slackDisplayName', '')}\n"
            f"Timezone: {user.get('timezone', '')}\n"
            f"Calendar ID: {user.get('calendarId', '')}"
        ),
        "sensitive_flags": [],
    }


def _doc_from_message(message: dict) -> dict:
    ts_iso = datetime.fromtimestamp(message["timestamp"] / 1000, tz=UTC).isoformat()
    return {
        "id": f"slack_{message['channelId']}_{message['timestamp']}_{message['userId']}",
        "source": "migration_slack",
        "filename": "slack_messages",
        "title": f"Slack {message['channelId']} — {message.get('displayName', message['userId'])}",
        "type": "slack_message",
        "role": "",
        "author": message["userId"],
        "timestamp": ts_iso,
        "tags": ["slack", message["channelId"]],
        "content": message.get("text", ""),
        "sensitive_flags": [],
    }


def _doc_from_meeting(meeting: dict) -> dict:
    return {
        "id": f"meeting_{meeting['meetingId']}",
        "source": "migration_meeting",
        "filename": "meetings",
        "title": meeting.get("title", meeting["meetingId"]),
        "type": "meeting",
        "role": "",
        "author": "",
        "timestamp": meeting.get("startTime", ""),
        "tags": ["meeting", meeting.get("status", "unknown")],
        "content": (
            f"Agenda: {meeting.get('agenda', '')}\n"
            f"Notes: {meeting.get('notes', '')}\n"
            f"Attendees: {', '.join(meeting.get('attendees', []))}"
        ),
        "sensitive_flags": [],
    }


def _doc_from_decision(decision: dict) -> dict:
    return {
        "id": f"decision_{decision['decisionId']}",
        "source": "migration_decision",
        "filename": "decisions",
        "title": f"Decision {decision['decisionId']}",
        "type": "decision",
        "role": "",
        "author": decision.get("madeBy", ""),
        "timestamp": decision.get("timestamp", ""),
        "tags": ["decision", decision.get("meetingId", "")],
        "content": (
            f"Decision: {decision.get('text', '')}\n"
            f"Evidence: {', '.join(decision.get('evidence', []))}"
        ),
        "sensitive_flags": [],
    }


def _doc_from_brief(brief: dict) -> dict:
    return {
        "id": f"brief_{brief['briefId']}",
        "source": "migration_agent_brief",
        "filename": "agent_briefs",
        "title": f"Brief {brief['briefId']}",
        "type": "agent_brief",
        "role": "",
        "author": brief.get("userId", ""),
        "timestamp": brief.get("generatedAt", ""),
        "tags": ["brief"],
        "content": (
            f"Summary: {brief.get('summary', '')}\n"
            f"Conflicts: {'; '.join(brief.get('conflicts', []))}\n"
            f"Action items: {'; '.join(brief.get('actionItems', []))}"
        ),
        "sensitive_flags": [],
    }


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    docs: list[dict] = []

    docs.extend(_doc_from_user(user) for user in USERS)
    docs.extend(_doc_from_message(message) for message in SLACK_MESSAGES)
    docs.extend(_doc_from_meeting(meeting) for meeting in MEETINGS)
    docs.extend(_doc_from_decision(decision) for decision in DECISIONS)
    docs.extend(_doc_from_brief(brief) for brief in AGENT_BRIEFS)

    db["documents"].delete_many({"source": {"$regex": r"^migration_"}})

    ops = []
    for doc in docs:
        payload = dict(doc)
        payload["seeded_at"] = now
        payload["updatedAt"] = now
        ops.append(
            UpdateOne(
                {"id": payload["id"]},
                {"$set": payload, "$setOnInsert": {"createdAt": now}},
                upsert=True,
            )
        )

    result = db["documents"].bulk_write(ops) if ops else None
    if not result:
        return 0
    return result.upserted_count + result.modified_count
