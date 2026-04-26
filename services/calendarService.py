from typing import Any

from services.calendar_service import add_reminder, create_event


def createEvent(userId: str, eventDetails: dict[str, Any]) -> dict:
    """
    Backward-compatible wrapper around services.calendar_service.create_event().
    """
    _ = userId  # Single-account calendar integration keeps one authenticated account.
    timezone = (
        eventDetails.get("timezone")
        or eventDetails.get("start", {}).get("timeZone")
        or eventDetails.get("end", {}).get("timeZone")
        or "UTC"
    )
    attendees = eventDetails.get("attendees", [])
    attendee_emails = [
        attendee["email"] if isinstance(attendee, dict) else str(attendee)
        for attendee in attendees
    ]

    details = {
        "summary": eventDetails["summary"],
        "description": eventDetails.get("description", ""),
        "start": eventDetails["start"]["dateTime"],
        "end": eventDetails["end"]["dateTime"],
        "timezone": timezone,
        "attendees": attendee_emails,
    }
    return create_event(details)


def updateEvent(userId: str, calendarEventId: str, updates: dict[str, Any]) -> dict:
    """
    Backward-compatible wrapper around services.calendar_service.add_reminder().
    Supports reminder-only patches.
    """
    _ = userId
    reminders = updates.get("reminders", {}).get("overrides")
    if reminders is None:
        raise ValueError("updateEvent only supports reminder overrides in this adapter.")
    return add_reminder(calendarEventId, reminders)
