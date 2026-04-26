import logging
import os
from datetime import UTC, datetime

from pymongo import MongoClient

from services.google_auth import get_calendar_service

_LOGGER = logging.getLogger("calendar_service")


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _update_meeting_event_id(summary: str, event_id: str) -> None:
    try:
        db = _get_db()
    except Exception:
        return

    db["meetings"].update_one(
        {"title": summary},
        {"$set": {"calendarEventId": event_id, "calendarUpdatedAt": datetime.now(UTC).isoformat()}},
    )


def create_event(event_details: dict) -> dict:
    """
    event_details = {
        "summary": str,
        "description": str,           # optional
        "start": "2024-05-15T10:00:00",
        "end":   "2024-05-15T10:30:00",
        "timezone": "America/Los_Angeles",  # optional, defaults to UTC
        "attendees": ["email1", "email2"],  # optional
        "reminders": [                      # optional
            {"method": "popup", "minutes": 10}
        ]
    }
    """
    timezone = event_details.get("timezone", "UTC")
    attendees_raw = event_details.get("attendees", []) or []
    body = {
        "summary": event_details["summary"],
        "description": event_details.get("description", ""),
        "start": {"dateTime": event_details["start"], "timeZone": timezone},
        "end": {"dateTime": event_details["end"], "timeZone": timezone},
        "attendees": [{"email": email} for email in attendees_raw],
    }

    reminders = event_details.get("reminders")
    if reminders:
        body["reminders"] = {"useDefault": False, "overrides": reminders}

    _LOGGER.info(
        "Calendar create_event request | "
        f"summary='{event_details['summary']}' | "
        f"start={event_details['start']} | end={event_details['end']} | "
        f"timezone={timezone} | attendees={attendees_raw} | "
        f"reminders={reminders or []}"
    )

    service = get_calendar_service()
    created = service.events().insert(calendarId="primary", body=body).execute()

    organizer_email = (created.get("organizer") or {}).get("email", "")
    _LOGGER.info(
        "Calendar create_event success | "
        f"eventId={created.get('id', '')} | htmlLink={created.get('htmlLink', '')} | "
        f"organizer={organizer_email} | status={created.get('status', '')} | "
        f"summary='{created.get('summary', '')}'"
    )

    _update_meeting_event_id(event_details["summary"], created.get("id", ""))
    return created


def add_reminder(event_id: str, reminders: list[dict]) -> dict:
    """
    reminders = [
        {"method": "popup", "minutes": 10},
        {"method": "email", "minutes": 60}
    ]
    Allowed methods: "popup", "email"
    Minutes: how long before the event to trigger
    """
    allowed_methods = {"popup", "email"}
    for reminder in reminders:
        method = reminder.get("method")
        minutes = reminder.get("minutes")
        if method not in allowed_methods:
            raise ValueError("Reminder method must be one of: popup, email")
        if not isinstance(minutes, int) or minutes < 0:
            raise ValueError("Reminder minutes must be a non-negative integer")

    body = {
        "reminders": {
            "useDefault": False,
            "overrides": reminders,
        }
    }
    service = get_calendar_service()
    return service.events().patch(
        calendarId="primary",
        eventId=event_id,
        body=body,
    ).execute()


def list_events(
    *,
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 10,
    query: str | None = None,
) -> list[dict]:
    """
    Read calendar events using Google Calendar events.list().

    Parameters are passed through to Google Calendar with sensible defaults:
    - singleEvents=True
    - orderBy="startTime"
    """
    request_kwargs: dict = {
        "calendarId": "primary",
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": max(1, int(max_results)),
    }
    if time_min:
        request_kwargs["timeMin"] = time_min
    if time_max:
        request_kwargs["timeMax"] = time_max
    if query:
        request_kwargs["q"] = query

    service = get_calendar_service()
    response = service.events().list(**request_kwargs).execute()
    return response.get("items", [])


def get_event(event_id: str) -> dict:
    """Read one calendar event using Google Calendar events.get()."""
    if not event_id:
        raise ValueError("event_id is required")
    service = get_calendar_service()
    return service.events().get(calendarId="primary", eventId=event_id).execute()
