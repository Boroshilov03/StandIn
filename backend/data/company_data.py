"""
NovaLoop — Checkout AI Assistant
Seeded company data for StandIn demo scenario.
Project: Launch Alpha  |  Deadline: Monday 2026-04-28 09:00
"""

# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------
USERS = {
    "alice.chen": {
        "id": "alice.chen",
        "name": "Alice Chen",
        "role": "Product Manager",
        "email": "alice.chen@novaloop.io",
        "team": "Product",
        "agent": "product_delegate",
        "agentverse_address": "",
    },
    "derek.vasquez": {
        "id": "derek.vasquez",
        "name": "Derek Vasquez",
        "role": "Lead Engineer",
        "email": "derek.vasquez@novaloop.io",
        "team": "Engineering",
        "agent": "engineering_delegate",
        "agentverse_address": "",
    },
    "priya.mehta": {
        "id": "priya.mehta",
        "name": "Priya Mehta",
        "role": "Design Lead",
        "email": "priya.mehta@novaloop.io",
        "team": "Design",
        "agent": "design_delegate",
        "agentverse_address": "",
    },
    "sam.okafor": {
        "id": "sam.okafor",
        "name": "Sam Okafor",
        "role": "GTM Manager",
        "email": "sam.okafor@novaloop.io",
        "team": "GTM",
        "agent": "gtm_delegate",
        "agentverse_address": "",
    },
    "kai.torres": {
        "id": "kai.torres",
        "name": "Kai Torres",
        "role": "QA Engineer",
        "email": "kai.torres@novaloop.io",
        "team": "Engineering",
        "agent": None,
        "agentverse_address": "",
    },
}

# ---------------------------------------------------------------------------
# CALENDAR
# ---------------------------------------------------------------------------
CALENDAR = {
    "launch_sync_001": {
        "id": "launch_sync_001",
        "title": "Launch Alpha — Go/No-Go Sync",
        "date": "2026-04-28",
        "time": "09:00",
        "timezone": "America/Los_Angeles",
        "duration_minutes": 30,
        "attendees": ["alice.chen", "derek.vasquez", "priya.mehta", "sam.okafor"],
        "organizer": "alice.chen",
        "location": "Google Meet",
        "agenda": [
            "Engineering: deployment readiness + API status",
            "Design: final asset sign-off",
            "GTM: launch email and comms status",
            "Product: go/no-go decision",
        ],
        "description": (
            "Final pre-launch sync before 9 AM Monday release of "
            "Checkout AI Assistant. All teams confirm ready status."
        ),
        "status": "confirmed",
    },
    "design_review_002": {
        "id": "design_review_002",
        "title": "Launch Page Final Design Review",
        "date": "2026-04-24",
        "time": "15:00",
        "timezone": "America/Los_Angeles",
        "duration_minutes": 45,
        "attendees": ["priya.mehta", "alice.chen", "sam.okafor"],
        "organizer": "priya.mehta",
        "location": "Zoom",
        "agenda": [
            "Review final launch page mockups",
            "Confirm copy and CTAs",
            "Sign off on asset package",
        ],
        "description": "Design final review before engineering handoff.",
        "status": "completed",
    },
    "eng_standup_003": {
        "id": "eng_standup_003",
        "title": "Engineering Daily Standup",
        "date": "2026-04-25",
        "time": "09:30",
        "timezone": "America/Los_Angeles",
        "duration_minutes": 15,
        "attendees": ["derek.vasquez", "kai.torres"],
        "organizer": "derek.vasquez",
        "location": "Slack Huddle",
        "agenda": [
            "API v2 migration status",
            "Launch page integration blocker",
            "QA sign-off timeline",
        ],
        "description": "Daily engineering sync — escalated due to overnight API change.",
        "status": "confirmed",
    },
}

# ---------------------------------------------------------------------------
# SLACK
# ---------------------------------------------------------------------------
SLACK = {
    # CRITICAL: seeded conflict — Design says ready
    "msg_design_launch_ready": {
        "id": "msg_design_launch_ready",
        "channel": "#launch-alpha",
        "sender": "priya.mehta",
        "sender_name": "Priya Mehta",
        "timestamp": "2026-04-25T08:47:00Z",
        "content": "Launch page is final and ready to ship. All assets approved by Alice. Handing off to Engineering for final integration check.",
        "reactions": [{"emoji": "white_check_mark", "count": 3}],
        "thread": [],
        "source_doc": "design_asset_note",
        "role": "Design",
    },
    # CRITICAL: seeded conflict — Engineering mentions API change
    "msg_eng_api_change": {
        "id": "msg_eng_api_change",
        "channel": "#engineering",
        "sender": "derek.vasquez",
        "sender_name": "Derek Vasquez",
        "timestamp": "2026-04-25T02:18:00Z",
        "content": (
            "@channel Heads up — the checkout API endpoint was migrated last night. "
            "It is now /v2/checkout (was /v1/checkout). The launch page integration "
            "still calls the old endpoint. Filed NOVA-142. This is a blocker for Monday."
        ),
        "reactions": [{"emoji": "rotating_light", "count": 1}],
        "thread": [
            {
                "sender": "kai.torres",
                "timestamp": "2026-04-25T07:52:00Z",
                "content": "Confirmed — QA smoke test on staging fails at checkout with 404. Need integration fix before I can sign off.",
            }
        ],
        "source_doc": "api_contract_change",
        "role": "Engineering",
    },
    "msg_gtm_email_preview": {
        "id": "msg_gtm_email_preview",
        "channel": "#launch-alpha",
        "sender": "sam.okafor",
        "sender_name": "Sam Okafor",
        "timestamp": "2026-04-25T09:10:00Z",
        "content": "Launch email drafted and in review. Waiting on pricing sign-off from legal before we can schedule the send.",
        "reactions": [],
        "thread": [],
        "source_doc": "gtm_notes",
        "role": "GTM",
    },
    "msg_alice_status_check": {
        "id": "msg_alice_status_check",
        "channel": "#launch-alpha",
        "sender": "alice.chen",
        "sender_name": "Alice Chen",
        "timestamp": "2026-04-25T09:00:00Z",
        "content": "Good morning everyone. Monday is 48 hours out. Needs: final eng sign-off, QA green, launch email approved. Derek what's the status on NOVA-142?",
        "reactions": [],
        "thread": [
            {
                "sender": "derek.vasquez",
                "timestamp": "2026-04-25T09:05:00Z",
                "content": "Still blocked. The v2 migration happened overnight, launch page integration needs an update before it'll work. I have a fix in progress but it's not tested yet.",
            }
        ],
        "source_doc": None,
        "role": "Product",
    },
    "msg_qa_sign_off_hold": {
        "id": "msg_qa_sign_off_hold",
        "channel": "#qa",
        "sender": "kai.torres",
        "sender_name": "Kai Torres",
        "timestamp": "2026-04-25T08:00:00Z",
        "content": "QA pass on checkout flow is on hold until NOVA-142 is resolved. Smoke test failing at /v2/checkout. Will rerun as soon as Derek merges the fix.",
        "reactions": [],
        "thread": [],
        "source_doc": "qa_bug_report",
        "role": "Engineering",
    },
}

# ---------------------------------------------------------------------------
# JIRA
# ---------------------------------------------------------------------------
JIRA = {
    # CRITICAL: seeded conflict — blocked ticket
    "NOVA-142": {
        "id": "NOVA-142",
        "title": "Update launch page integration for v2 checkout API",
        "status": "blocked",
        "priority": "critical",
        "assignee": "derek.vasquez",
        "reporter": "derek.vasquez",
        "created": "2026-04-25T02:30:00Z",
        "updated": "2026-04-25T09:05:00Z",
        "description": (
            "Checkout endpoint changed from /v1/checkout to /v2/checkout last night. "
            "The launch page still calls the old /v1/checkout endpoint. "
            "Integration will fail at checkout on launch unless this is updated."
        ),
        "reason": "Checkout endpoint changed from /v1/checkout to /v2/checkout last night.",
        "labels": ["launch-alpha", "blocker", "api-v2", "launch-page"],
        "sprint": "Launch Alpha Sprint 4",
        "epic": "NOVA-LAUNCH-ALPHA",
        "story_points": 3,
        "source_doc": "api_contract_change",
        "risk": "high",
    },
    "NOVA-139": {
        "id": "NOVA-139",
        "title": "Implement Gemini summarization for checkout flow",
        "status": "done",
        "priority": "high",
        "assignee": "derek.vasquez",
        "reporter": "alice.chen",
        "created": "2026-04-20T10:00:00Z",
        "updated": "2026-04-24T17:30:00Z",
        "description": "Integrate Gemini API to generate natural-language checkout step summaries for the AI assistant.",
        "labels": ["launch-alpha", "gemini", "ai-assistant"],
        "sprint": "Launch Alpha Sprint 4",
        "epic": "NOVA-LAUNCH-ALPHA",
        "story_points": 5,
        "source_doc": None,
        "risk": "low",
    },
    "NOVA-140": {
        "id": "NOVA-140",
        "title": "Design QA handoff — launch page assets",
        "status": "done",
        "priority": "high",
        "assignee": "priya.mehta",
        "reporter": "priya.mehta",
        "created": "2026-04-22T09:00:00Z",
        "updated": "2026-04-24T16:00:00Z",
        "description": "Deliver final launch page design assets and spec to Engineering for implementation review.",
        "labels": ["launch-alpha", "design", "launch-page"],
        "sprint": "Launch Alpha Sprint 4",
        "epic": "NOVA-LAUNCH-ALPHA",
        "story_points": 2,
        "source_doc": "design_asset_note",
        "risk": "low",
    },
    "NOVA-141": {
        "id": "NOVA-141",
        "title": "GTM launch email — legal and pricing review",
        "status": "in_review",
        "priority": "high",
        "assignee": "sam.okafor",
        "reporter": "sam.okafor",
        "created": "2026-04-23T11:00:00Z",
        "updated": "2026-04-25T08:45:00Z",
        "description": "Launch email draft requires pricing confirmation and legal sign-off before scheduling send.",
        "labels": ["launch-alpha", "gtm", "email", "legal"],
        "sprint": "Launch Alpha Sprint 4",
        "epic": "NOVA-LAUNCH-ALPHA",
        "story_points": 2,
        "source_doc": "gtm_notes",
        "risk": "medium",
    },
    "NOVA-143": {
        "id": "NOVA-143",
        "title": "QA smoke test sign-off — checkout flow",
        "status": "blocked",
        "priority": "critical",
        "assignee": "kai.torres",
        "reporter": "kai.torres",
        "created": "2026-04-25T08:05:00Z",
        "updated": "2026-04-25T08:05:00Z",
        "description": "Smoke test cannot complete while NOVA-142 is unresolved. Blocked on engineering fix for v2 API integration.",
        "labels": ["launch-alpha", "qa", "blocked-by-nova-142"],
        "sprint": "Launch Alpha Sprint 4",
        "epic": "NOVA-LAUNCH-ALPHA",
        "story_points": 1,
        "source_doc": "qa_bug_report",
        "risk": "high",
    },
}

# ---------------------------------------------------------------------------
# AGENT_ADDRESSES  (fill in after Agentverse deployment)
# ---------------------------------------------------------------------------
AGENT_ADDRESSES = {
    "orchestrator": "",
    "engineering_delegate": "",
    "design_delegate": "",
    "product_delegate": "",
    "gtm_delegate": "",
    "verifier": "",
    "escalation": "",
}
