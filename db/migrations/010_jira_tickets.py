"""
Seeds the `standin.jira_tickets` collection with the StandIn launch scenario.

Story (matches 007_slack_messages):
- AUTH-101 — Ben owns the OAuth-token-on-handoff blocker (high priority bug).
- AUTH-102 — James investigates the related frontend token refresh issue.
- AUTH-103 — Priya runs the auth regression suite, blocked on AUTH-101 patch.
- DEMO-201 — Alice tracks the v1 demo readiness umbrella story.
- OPS-301  — Sara tracks vendor contract signing logistics.

Assignees use the same `_id`s as the `users` collection seeded by 001_users.
This way, "schedule a meeting with Ben to discuss the blocker" can resolve
Ben (user_ben) and use his email (ben@standin.ai) without any hardcoded
persona table in the orchestrator.
"""

from datetime import UTC, datetime

from pymongo import UpdateOne


JIRA_TICKETS = [
    {
        "issueKey": "AUTH-101",
        "summary": "OAuth tokens not invalidating on delegate handoff",
        "issuetype": "Bug",
        "priority": "High",
        "status": "In Review",
        "labels": ["auth", "blocker", "v1"],
        "assignee": "user_ben",
        "assigneeName": "Ben Okafor",
        "reporter": "user_priya",
        "reporterName": "Priya Nair",
        "url": "https://standinorg.atlassian.net/browse/AUTH-101",
        "description": (
            "Auth middleware leaks token state across delegate handoffs — stale "
            "auth contexts can be inherited. Ben repro'd locally and isolated "
            "the regression to the token refresh interceptor. Patch up as PR "
            "#204; pending QA regression run."
        ),
        "createdAt": "2026-05-04T09:08:00-07:00",
        "updatedAt": "2026-05-06T09:17:00-07:00",
        "sprintName": "Sprint 1",
        "linkedSlackThread": "msg_001",
    },
    {
        "issueKey": "AUTH-102",
        "summary": "Frontend token refresh inconsistency after handoff",
        "issuetype": "Bug",
        "priority": "Medium",
        "status": "Done",
        "labels": ["auth", "frontend"],
        "assignee": "user_james",
        "assigneeName": "James Wu",
        "reporter": "user_james",
        "reporterName": "James Wu",
        "url": "https://standinorg.atlassian.net/browse/AUTH-102",
        "description": (
            "Frontend client showed token state bleed after delegate handoff. "
            "Root-caused to the same interceptor as AUTH-101 — resolved by "
            "PR #204."
        ),
        "createdAt": "2026-05-04T09:31:00-07:00",
        "updatedAt": "2026-05-06T09:29:00-07:00",
        "sprintName": "Sprint 1",
    },
    {
        "issueKey": "AUTH-103",
        "summary": "QA auth regression pack — token expiry and handoff",
        "issuetype": "Task",
        "priority": "High",
        "status": "In Progress",
        "labels": ["qa", "regression", "v1"],
        "assignee": "user_priya",
        "assigneeName": "Priya Nair",
        "reporter": "user_priya",
        "reporterName": "Priya Nair",
        "url": "https://standinorg.atlassian.net/browse/AUTH-103",
        "description": (
            "Run regression suite against PR #204. Currently 11/12 passing; "
            "one flaky test on artificial sub-30s token lifetimes. Tracking as "
            "minor caveat, not a launch blocker."
        ),
        "createdAt": "2026-05-05T11:06:00-07:00",
        "updatedAt": "2026-05-07T09:11:00-07:00",
        "sprintName": "Sprint 1",
    },
    {
        "issueKey": "DEMO-201",
        "summary": "v1 demo readiness umbrella",
        "issuetype": "Story",
        "priority": "High",
        "status": "In Progress",
        "labels": ["demo", "v1"],
        "assignee": "user_alice",
        "assigneeName": "Alice Chen",
        "reporter": "user_alice",
        "reporterName": "Alice Chen",
        "url": "https://standinorg.atlassian.net/browse/DEMO-201",
        "description": (
            "v1 scope locked: status agent, conflict detection, action "
            "dispatch, RAG evidence pipeline, personal delegate network. "
            "Handoff UI deferred to v1.1. Dry run passed; staging seed loaded."
        ),
        "createdAt": "2026-05-04T10:04:00-07:00",
        "updatedAt": "2026-05-08T11:22:00-07:00",
        "sprintName": "Sprint 1",
    },
    {
        "issueKey": "OPS-301",
        "summary": "Vendor contract signing — extension and DPA",
        "issuetype": "Task",
        "priority": "Medium",
        "status": "Done",
        "labels": ["ops", "vendor"],
        "assignee": "user_sara",
        "assigneeName": "Sara Malik",
        "reporter": "user_sara",
        "reporterName": "Sara Malik",
        "url": "https://standinorg.atlassian.net/browse/OPS-301",
        "description": (
            "Negotiate +3 day vendor extension to absorb the demo scope tighten. "
            "Call rescheduled Thu 2pm; signing Monday; DPA signature handled "
            "async."
        ),
        "createdAt": "2026-05-05T10:02:00-07:00",
        "updatedAt": "2026-05-07T14:48:00-07:00",
        "sprintName": "Sprint 1",
    },
]


def migrate(db) -> int:
    now = datetime.now(UTC).isoformat()
    ops = []
    for ticket in JIRA_TICKETS:
        payload = dict(ticket)
        payload["_id"] = ticket["issueKey"]
        payload["seededAt"] = now
        payload["updatedAt"] = ticket.get("updatedAt", now)
        created_at = ticket.get("createdAt", now)
        payload.pop("createdAt", None)
        ops.append(
            UpdateOne(
                {"_id": payload["_id"]},
                {
                    "$set": payload,
                    "$setOnInsert": {"createdAt": created_at},
                },
                upsert=True,
            )
        )
    if not ops:
        return 0
    result = db["jira_tickets"].bulk_write(ops)
    return result.upserted_count + result.modified_count
