import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.google_auth import get_calendar_service


load_dotenv(ROOT / ".env")


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _already_exists(service, summary: str, start_dt: str, end_dt: str) -> bool:
    time_min = f"{start_dt}Z"
    time_max = f"{end_dt}Z"
    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        q=summary,
        singleEvents=True,
    ).execute()
    for item in result.get("items", []):
        if item.get("summary") == summary:
            return True
    return False


def _store_event_id(summary: str, event_id: str) -> None:
    try:
        db = _get_db()
        db["meetings"].update_one(
            {"title": summary},
            {"$set": {"calendarEventId": event_id, "calendarUpdatedAt": datetime.now(UTC).isoformat()}},
        )
    except Exception as exc:
        print(f"Warning: could not update meetings collection for '{summary}': {exc}")


def run() -> None:
    service = get_calendar_service()
    events = [
        {
            "summary": "Meridian Launch Sync",
            "description": "Weekly launch coordination. Auth bug impact on demo timeline.",
            "start": "2026-04-25T09:00:00",
            "end": "2026-04-25T09:30:00",
            "attendees": ["alice@example.com", "ben@example.com", "priya@example.com"],
            "reminders": [{"method": "popup", "minutes": 10}],
        },
        {
            "summary": "Auth Bug Triage",
            "description": "PR #204 review — token refresh interceptor fix. Ben leading.",
            "start": "2026-04-26T14:00:00",
            "end": "2026-04-26T14:45:00",
            "attendees": ["ben@example.com", "james@example.com", "priya@example.com"],
            "reminders": [{"method": "popup", "minutes": 5}],
        },
        {
            "summary": "Vendor Contract Call",
            "description": "Infrastructure provider — confirm extension, DPA discussion.",
            "start": "2026-04-27T14:00:00",
            "end": "2026-04-27T15:00:00",
            "attendees": ["sara@example.com", "alice@example.com"],
            "reminders": [
                {"method": "popup", "minutes": 15},
                {"method": "email", "minutes": 60},
            ],
        },
        {
            "summary": "Demo Dry Run",
            "description": "Full walkthrough: status query, conflict detection, action dispatch.",
            "start": "2026-04-29T10:00:00",
            "end": "2026-04-29T11:00:00",
            "attendees": ["alice@example.com", "ben@example.com", "priya@example.com", "james@example.com"],
            "reminders": [{"method": "popup", "minutes": 10}],
        },
        {
            "summary": "Board Demo — StandIn v1",
            "description": "Live demo to board. Scope: status agent, conflict detection, action dispatch.",
            "start": "2026-04-30T13:00:00",
            "end": "2026-04-30T14:00:00",
            "attendees": ["alice@example.com", "ben@example.com"],
            "reminders": [
                {"method": "popup", "minutes": 30},
                {"method": "email", "minutes": 1440},
            ],
        },
        {
            "summary": "Post-Launch Retrospective",
            "description": "Team retro — what went well, what didn't, v1.1 priorities.",
            "start": "2026-04-30T16:00:00",
            "end": "2026-04-30T17:00:00",
            "attendees": [
                "alice@example.com",
                "ben@example.com",
                "sara@example.com",
                "priya@example.com",
                "james@example.com",
            ],
            "reminders": [{"method": "popup", "minutes": 10}],
        },
    ]

    created = 0
    skipped = 0
    for event in events:
        if _already_exists(service, event["summary"], event["start"], event["end"]):
            print(f"Skipping existing event: {event['summary']}")
            skipped += 1
            continue

        body = {
            "summary": event["summary"],
            "description": event.get("description", ""),
            "start": {"dateTime": event["start"], "timeZone": "UTC"},
            "end": {"dateTime": event["end"], "timeZone": "UTC"},
            "attendees": [{"email": email} for email in event.get("attendees", [])],
            "reminders": {"useDefault": False, "overrides": event.get("reminders", [])},
        }
        created_event = service.events().insert(calendarId="primary", body=body).execute()
        _store_event_id(event["summary"], created_event["id"])
        print(f"Created event: {event['summary']} -> {created_event['id']}")
        created += 1

    print(f"seed_calendar complete: created={created}, skipped={skipped}")


if __name__ == "__main__":
    run()
