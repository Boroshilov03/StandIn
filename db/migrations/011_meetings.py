"""
Replaces the `standin.meetings` collection with StandIn-team scheduled meetings
tied to the auth-bug + v1 demo storyline (matches 007_slack_messages and the
AUTH-101..103 / DEMO-201 / OPS-301 tickets in 010_jira_tickets).

This migration drops + reseeds the collection so it stays in sync with the
StandIn personas regardless of any earlier (legacy NovaLoop) seed.
"""

from datetime import UTC, datetime


MEETINGS = [
    {
        "meetingId": "mtg-auth-bug-triage",
        "title": "Auth bug triage — AUTH-101",
        "startTime": "2026-05-04T10:30:00-07:00",
        "endTime": "2026-05-04T11:00:00-07:00",
        "timezone": "America/Los_Angeles",
        "organizer": "user_alice",
        "attendees": ["user_alice", "user_ben", "user_priya"],
        "status": "completed",
        "agenda": "Triage OAuth-token-on-handoff bug, agree owner and ETA.",
        "notes": "Ben owns AUTH-101, ETA 3-4 days. Priya queues regression pack.",
        "linkedTickets": ["AUTH-101"],
    },
    {
        "meetingId": "mtg-vendor-call",
        "title": "Vendor contract — extension call",
        "startTime": "2026-05-07T14:00:00-07:00",
        "endTime": "2026-05-07T14:45:00-07:00",
        "timezone": "America/Los_Angeles",
        "organizer": "user_sara",
        "attendees": ["user_sara", "user_alice"],
        "status": "completed",
        "agenda": "Negotiate +3 day extension to absorb v1 scope tighten.",
        "notes": "Vendor agreed; signing Monday. DPA handled async.",
        "linkedTickets": ["OPS-301"],
    },
    {
        "meetingId": "mtg-demo-dry-run",
        "title": "v1 demo dry run",
        "startTime": "2026-05-08T10:00:00-07:00",
        "endTime": "2026-05-08T10:45:00-07:00",
        "timezone": "America/Los_Angeles",
        "organizer": "user_alice",
        "attendees": ["user_alice", "user_ben", "user_priya", "user_james"],
        "status": "completed",
        "agenda": "Run through status query, conflict detection, action dispatch on staging.",
        "notes": "Dry run passed. Minor UI label fix logged for James.",
        "linkedTickets": ["DEMO-201"],
    },
    {
        "meetingId": "mtg-launch-monday",
        "title": "v1 Launch — Monday go-live",
        "startTime": "2026-05-11T09:00:00-07:00",
        "endTime": "2026-05-11T09:30:00-07:00",
        "timezone": "America/Los_Angeles",
        "organizer": "user_alice",
        "attendees": ["user_alice", "user_ben", "user_sara", "user_james", "user_priya"],
        "status": "scheduled",
        "agenda": "v1 launch comms; vendor signing follow-up; team retro placeholder.",
        "linkedTickets": ["DEMO-201", "OPS-301"],
    },
    {
        "meetingId": "mtg-team-retro",
        "title": "Post-launch retro",
        "startTime": "2026-05-11T16:00:00-07:00",
        "endTime": "2026-05-11T17:00:00-07:00",
        "timezone": "America/Los_Angeles",
        "organizer": "user_sara",
        "attendees": ["user_alice", "user_ben", "user_sara", "user_james", "user_priya"],
        "status": "scheduled",
        "agenda": "What worked, what didn't, what we change for v1.1 (handoff UI).",
        "linkedTickets": ["DEMO-201"],
    },
]


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    db["meetings"].drop()
    docs = []
    for meeting in MEETINGS:
        payload = dict(meeting)
        payload["createdAt"] = now
        payload["updatedAt"] = now
        docs.append(payload)
    if not docs:
        return 0
    db["meetings"].insert_many(docs)
    return len(docs)
