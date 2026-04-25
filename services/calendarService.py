import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _refresh_token_key(user_id: str) -> str:
    return f"USER_{user_id.replace('.', '_').replace('-', '_').upper()}_REFRESH_TOKEN"


def _calendar_client_for_user(user_id: str):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    refresh_token = os.getenv(_refresh_token_key(user_id), "")
    if not client_id or not client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set.")
    if not refresh_token:
        raise RuntimeError(f"Missing refresh token env var for user '{user_id}'.")

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[CALENDAR_SCOPE],
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def createEvent(userId: str, eventDetails: dict[str, Any]) -> dict:
    """
    Creates an event on behalf of userId and optionally stores returned id to meetings.
    eventDetails supports:
      - summary, description
      - start: {dateTime, timeZone}
      - end: {dateTime, timeZone}
      - attendees: [{email}]
      - calendarId (optional override)
      - meetingId (optional, for writing calendarEventId back to Mongo meetings)
    """
    db = _get_db()
    user = db["users"].find_one({"_id": userId}, {"_id": 0, "calendarId": 1})
    if not user:
        raise ValueError(f"User '{userId}' not found.")

    service = _calendar_client_for_user(userId)
    calendar_id = eventDetails.get("calendarId") or user["calendarId"]
    body = {
        "summary": eventDetails["summary"],
        "description": eventDetails.get("description", ""),
        "start": eventDetails["start"],
        "end": eventDetails["end"],
        "attendees": eventDetails.get("attendees", []),
    }

    created = service.events().insert(calendarId=calendar_id, body=body).execute()

    meeting_id = eventDetails.get("meetingId")
    if meeting_id:
        db["meetings"].update_one(
            {"meetingId": meeting_id},
            {
                "$set": {
                    "calendarEventId": created.get("id"),
                    "calendarOwnerUserId": userId,
                    "calendarId": calendar_id,
                }
            },
        )
    return created


def updateEvent(userId: str, calendarEventId: str, updates: dict[str, Any]) -> dict:
    """
    Patches an existing event using partial Calendar event body.
    """
    db = _get_db()
    user = db["users"].find_one({"_id": userId}, {"_id": 0, "calendarId": 1})
    if not user:
        raise ValueError(f"User '{userId}' not found.")

    service = _calendar_client_for_user(userId)
    updated = service.events().patch(
        calendarId=user["calendarId"], eventId=calendarEventId, body=updates
    ).execute()

    db["meetings"].update_many(
        {"calendarEventId": calendarEventId},
        {"$set": {"lastCalendarSyncBy": userId}},
    )
    return updated
