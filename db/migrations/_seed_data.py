from datetime import datetime


def _ts(dt_str: str) -> int:
    return int(datetime.fromisoformat(dt_str).timestamp() * 1000)


USERS = [
    {
        "_id": "alice.chen",
        "name": "Alice Chen",
        "email": "alice.chen@novaloop.io",
        "slackUserId": "U01ALICE01",
        "slackDisplayName": "Alice Chen",
        "avatarEmoji": ":grinning_cat:",
        "timezone": "America/Los_Angeles",
        "calendarId": "alice.chen@novaloop.io",
    },
    {
        "_id": "derek.vasquez",
        "name": "Derek Vasquez",
        "email": "derek.vasquez@novaloop.io",
        "slackUserId": "U01DEREK02",
        "slackDisplayName": "Derek Vasquez",
        "avatarEmoji": ":male-technologist:",
        "timezone": "America/Los_Angeles",
        "calendarId": "derek.vasquez@novaloop.io",
    },
    {
        "_id": "priya.mehta",
        "name": "Priya Mehta",
        "email": "priya.mehta@novaloop.io",
        "slackUserId": "U01PRIYA03",
        "slackDisplayName": "Priya Mehta",
        "avatarEmoji": ":art:",
        "timezone": "America/Los_Angeles",
        "calendarId": "priya.mehta@novaloop.io",
    },
    {
        "_id": "sam.okafor",
        "name": "Sam Okafor",
        "email": "sam.okafor@novaloop.io",
        "slackUserId": "U01SAM004",
        "slackDisplayName": "Sam Okafor",
        "avatarEmoji": ":rocket:",
        "timezone": "America/Los_Angeles",
        "calendarId": "sam.okafor@novaloop.io",
    },
    {
        "_id": "kai.torres",
        "name": "Kai Torres",
        "email": "kai.torres@novaloop.io",
        "slackUserId": "U01KAI005",
        "slackDisplayName": "Kai Torres",
        "avatarEmoji": ":microscope:",
        "timezone": "America/Los_Angeles",
        "calendarId": "kai.torres@novaloop.io",
    },
]

SLACK_CHANNELS = [
    {
        "channelId": "C01STANDUP1",
        "name": "#product-standup",
        "members": ["U01ALICE01", "U01DEREK02", "U01PRIYA03", "U01SAM004", "U01KAI005"],
    },
    {
        "channelId": "C01DECIDE02",
        "name": "#decisions-launch",
        "members": ["U01ALICE01", "U01DEREK02", "U01PRIYA03", "U01SAM004"],
    },
    {
        "channelId": "C01UPDATES3",
        "name": "#general-updates",
        "members": ["U01ALICE01", "U01DEREK02", "U01PRIYA03", "U01SAM004", "U01KAI005"],
    },
]

SLACK_MESSAGES = [
    # product-standup (14)
    {"channelId": "C01STANDUP1", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Standup: launch T-3 days, tracking engineering sign-off and GTM readiness.", "timestamp": _ts("2026-04-25T08:30:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "Blocker: checkout endpoint moved from /v1/checkout to /v2/checkout.", "timestamp": _ts("2026-04-25T08:31:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01KAI005", "displayName": "Kai Torres", "text": "QA smoke test failing with 404 until integration is updated.", "timestamp": _ts("2026-04-25T08:32:00+00:00"), "thread_ts": str(_ts("2026-04-25T08:31:00+00:00"))},
    {"channelId": "C01STANDUP1", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "Design handoff complete, assets and specs are in Drive.", "timestamp": _ts("2026-04-25T08:34:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "Launch email copy approved pending legal pricing wording.", "timestamp": _ts("2026-04-25T08:35:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "I can ship the API client patch by noon PT.", "timestamp": _ts("2026-04-25T08:36:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Action item: Derek + Kai pair test after patch merge.", "timestamp": _ts("2026-04-25T08:37:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01KAI005", "displayName": "Kai Torres", "text": "Booked test window 1:30pm PT.", "timestamp": _ts("2026-04-25T08:38:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Reminder: go/no-go sync Monday 9:00am PT.", "timestamp": _ts("2026-04-25T08:40:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "I have overlap with customer interview 9:00-9:30 Monday.", "timestamp": _ts("2026-04-25T08:42:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "I can join late if legal pre-brief runs over.", "timestamp": _ts("2026-04-25T08:43:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "Need explicit decision: delay launch if API fix fails QA?", "timestamp": _ts("2026-04-25T08:44:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Yes, if QA red we delay. I'll document in decisions channel.", "timestamp": _ts("2026-04-25T08:45:00+00:00")},
    {"channelId": "C01STANDUP1", "userId": "U01KAI005", "displayName": "Kai Torres", "text": "Acknowledged.", "timestamp": _ts("2026-04-25T08:46:00+00:00"), "thread_ts": str(_ts("2026-04-25T08:45:00+00:00"))},
    # decisions-launch (13)
    {"channelId": "C01DECIDE02", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Decision: launch is contingent on NOVA-142 and NOVA-143 closure.", "timestamp": _ts("2026-04-25T09:00:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "Decision input: API patch owner is Derek, ETA 12:00 PT.", "timestamp": _ts("2026-04-25T09:01:00+00:00"), "thread_ts": str(_ts("2026-04-25T09:00:00+00:00"))},
    {"channelId": "C01DECIDE02", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "Decision input: GTM send time shifts if launch shifts.", "timestamp": _ts("2026-04-25T09:02:00+00:00"), "thread_ts": str(_ts("2026-04-25T09:00:00+00:00"))},
    {"channelId": "C01DECIDE02", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "Decision: design considers launch page final with no further changes.", "timestamp": _ts("2026-04-25T09:05:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "Contradiction flagged: design-ready but API integration blocked.", "timestamp": _ts("2026-04-25T09:06:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Decision: schedule escalation with design+engineering only.", "timestamp": _ts("2026-04-25T09:07:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "Decision: hold outbound launch email until escalation outcome.", "timestamp": _ts("2026-04-25T09:09:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01KAI005", "displayName": "Kai Torres", "text": "Decision input: QA can complete regression in 45 min after patch.", "timestamp": _ts("2026-04-25T09:10:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Decision: if regression passes, proceed with Monday launch.", "timestamp": _ts("2026-04-25T09:11:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "Action item accepted: update hero CTA spec for v2 labels.", "timestamp": _ts("2026-04-25T09:12:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "Action item accepted: merge API path hotfix and notify QA.", "timestamp": _ts("2026-04-25T09:13:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "Action item accepted: rewrite send copy to remove hard date.", "timestamp": _ts("2026-04-25T09:14:00+00:00")},
    {"channelId": "C01DECIDE02", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Archived decision in weekly brief references.", "timestamp": _ts("2026-04-25T09:15:00+00:00")},
    # general-updates (12)
    {"channelId": "C01UPDATES3", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "General update: investor demo moved to Tuesday.", "timestamp": _ts("2026-04-25T10:00:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "General update: shipped final icon set to CDN.", "timestamp": _ts("2026-04-25T10:02:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01KAI005", "displayName": "Kai Torres", "text": "General update: nightly suite pass rate back to 96%.", "timestamp": _ts("2026-04-25T10:03:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "General update: patch branch open as feature/nova-142-fix.", "timestamp": _ts("2026-04-25T10:05:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "General update: customer advisory board notes uploaded.", "timestamp": _ts("2026-04-25T10:06:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "Schedule change: GTM review shifted to 11:30.", "timestamp": _ts("2026-04-25T10:10:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "Schedule change: design QA pairing moved to 1:45.", "timestamp": _ts("2026-04-25T10:11:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01KAI005", "displayName": "Kai Torres", "text": "Heads-up: I conflict with 2:00 PM bug triage if escalation runs long.", "timestamp": _ts("2026-04-25T10:12:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01DEREK02", "displayName": "Derek Vasquez", "text": "Need a decision on rollback criteria for checkout errors >1%.", "timestamp": _ts("2026-04-25T10:14:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01ALICE01", "displayName": "Alice Chen", "text": "Criteria approved: rollback if >1% errors for 10 minutes.", "timestamp": _ts("2026-04-25T10:15:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01SAM004", "displayName": "Sam Okafor", "text": "Reminder: press prep call tomorrow at 9:30.", "timestamp": _ts("2026-04-25T10:18:00+00:00")},
    {"channelId": "C01UPDATES3", "userId": "U01PRIYA03", "displayName": "Priya Mehta", "text": "Posting final launch page screenshot in #decisions-launch.", "timestamp": _ts("2026-04-25T10:20:00+00:00")},
]

MEETINGS = [
    {
        "meetingId": "mtg-standup-2026-04-25",
        "title": "Daily Product Standup",
        "startTime": "2026-04-25T09:30:00-07:00",
        "endTime": "2026-04-25T10:00:00-07:00",
        "attendees": ["alice.chen", "derek.vasquez", "priya.mehta", "sam.okafor", "kai.torres"],
        "status": "completed",
        "agenda": "Launch readiness updates and blocker triage.",
        "notes": "Engineering blocker NOVA-142 surfaced; QA blocked on validation.",
    },
    {
        "meetingId": "mtg-design-customer-overlap",
        "title": "Customer Discovery Interview",
        "startTime": "2026-04-28T09:00:00-07:00",
        "endTime": "2026-04-28T09:30:00-07:00",
        "attendees": ["priya.mehta", "alice.chen"],
        "status": "scheduled",
        "agenda": "Collect launch-page feedback from design partner.",
    },
    {
        "meetingId": "mtg-go-no-go-2026-04-28",
        "title": "Launch Alpha Go/No-Go",
        "startTime": "2026-04-28T09:00:00-07:00",
        "endTime": "2026-04-28T09:30:00-07:00",
        "attendees": ["alice.chen", "derek.vasquez", "priya.mehta", "sam.okafor"],
        "status": "scheduled",
        "agenda": "Final launch decision pending engineering and QA sign-off.",
    },
    {
        "meetingId": "mtg-escalation-2026-04-25",
        "title": "Design + Engineering Escalation",
        "startTime": "2026-04-25T13:00:00-07:00",
        "endTime": "2026-04-25T13:20:00-07:00",
        "attendees": ["derek.vasquez", "priya.mehta", "alice.chen"],
        "status": "scheduled",
        "agenda": "Resolve contradiction: design ready vs API blocker.",
    },
    {
        "meetingId": "mtg-bug-triage-overlap",
        "title": "Engineering Bug Triage",
        "startTime": "2026-04-25T13:15:00-07:00",
        "endTime": "2026-04-25T13:45:00-07:00",
        "attendees": ["derek.vasquez", "kai.torres"],
        "status": "scheduled",
        "agenda": "Triage top launch-critical defects.",
    },
    {
        "meetingId": "mtg-gtm-legal-review",
        "title": "GTM + Legal Pricing Review",
        "startTime": "2026-04-25T11:30:00-07:00",
        "endTime": "2026-04-25T12:00:00-07:00",
        "attendees": ["sam.okafor", "alice.chen"],
        "status": "scheduled",
        "agenda": "Approve launch email pricing and legal language.",
    },
]

DECISIONS = [
    {
        "decisionId": "dec-001",
        "meetingId": "mtg-standup-2026-04-25",
        "madeBy": "alice.chen",
        "text": "Launch is gated on NOVA-142 and QA pass before Monday.",
        "timestamp": "2026-04-25T09:45:00-07:00",
        "evidence": ["slack:C01DECIDE02:1745571600000", "meeting:mtg-standup-2026-04-25:notes"],
    },
    {
        "decisionId": "dec-002",
        "meetingId": "mtg-escalation-2026-04-25",
        "madeBy": "derek.vasquez",
        "text": "Engineering will merge API path hotfix by noon and notify QA immediately.",
        "timestamp": "2026-04-25T13:18:00-07:00",
        "evidence": ["slack:C01STANDUP1:1745570160000", "jira:NOVA-142"],
    },
    {
        "decisionId": "dec-003",
        "meetingId": "mtg-gtm-legal-review",
        "madeBy": "sam.okafor",
        "text": "Outbound launch email send is paused until product confirms no launch slip.",
        "timestamp": "2026-04-25T11:59:00-07:00",
        "evidence": ["slack:C01DECIDE02:1745572140000", "meeting:mtg-gtm-legal-review:agenda"],
    },
]

AGENT_BRIEFS = [
    {
        "briefId": "brief-alice-20260425-am",
        "userId": "alice.chen",
        "generatedAt": "2026-04-25T10:25:00-07:00",
        "meetingId": "mtg-go-no-go-2026-04-28",
        "summary": "Engineering and QA still blocked by API migration; GTM is ready pending legal copy.",
        "conflicts": ["Design reports launch page ready while Engineering reports integration blocker NOVA-142."],
        "actionItems": ["Run design+engineering escalation at 1:00 PM.", "Get QA rerun immediately after patch merge."],
        "sources": ["dec-001", "dec-002", "slack:C01STANDUP1:1745569860000"],
    },
    {
        "briefId": "brief-derek-20260425-am",
        "userId": "derek.vasquez",
        "generatedAt": "2026-04-25T10:25:00-07:00",
        "meetingId": "mtg-escalation-2026-04-25",
        "summary": "Primary task is API v2 hotfix; QA ready to validate once branch merges.",
        "conflicts": ["Overlap with bug triage at 1:15 PM may reduce escalation attendance."],
        "actionItems": ["Post branch status to #general-updates.", "Hand off test checklist to Kai."],
        "sources": ["slack:C01UPDATES3:1745576040000", "slack:C01UPDATES3:1745575920000"],
    },
]
