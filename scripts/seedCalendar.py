import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.calendarService import _get_db, createEvent  # noqa: E402


def _meeting_to_event(meeting: dict) -> dict:
    attendees = meeting.get("attendees", [])
    attendee_docs = list(_get_db()["users"].find({"_id": {"$in": attendees}}, {"_id": 0, "email": 1}))
    return {
        "meetingId": meeting["meetingId"],
        "summary": meeting["title"],
        "description": meeting.get("agenda", ""),
        "start": {"dateTime": meeting["startTime"], "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": meeting["endTime"], "timeZone": "America/Los_Angeles"},
        "attendees": [{"email": doc["email"]} for doc in attendee_docs],
    }


def run() -> None:
    db = _get_db()
    meetings = list(db["meetings"].find({}))
    created = 0
    skipped = 0
    for meeting in meetings:
        if meeting.get("calendarEventId"):
            skipped += 1
            continue
        owner = meeting.get("attendees", [None])[0]
        if not owner:
            skipped += 1
            continue
        event = createEvent(owner, _meeting_to_event(meeting))
        print(f"Created {meeting['meetingId']} -> {event.get('id')}")
        created += 1
    print(f"seedCalendar complete: created={created}, skipped={skipped}")


if __name__ == "__main__":
    run()
