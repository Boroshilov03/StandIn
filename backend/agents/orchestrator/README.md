# StandIn Orchestrator

StandIn Orchestrator is the ASI:One-facing coordination agent for this repo.

It accepts Chat Protocol messages and routes them to internal specialists:

- `status_agent` for live status, contradiction checks, and briefings
- `historical_agent` for prior decisions and document-backed history
- `perform_action` for Jira, Slack, meeting, and action-item requests

## Supported request types

- Current status and launch readiness questions
- Cross-team conflict and contradiction checks
- Historical decision lookups
- Action requests such as creating a Jira ticket or drafting Slack
- Executive-style briefings

## Notes

- Only the orchestrator is intended to be exposed through Agentverse / ASI:One.
- Internal agents stay private and are invoked by the orchestrator.
- `MONGODB_URI` is optional; without it, history uses fallback retrieval and actions remain mostly stubbed.

## Local run

From the repo root:

```powershell
.\.venv\Scripts\python backend\main.py
```

Then open the printed Agent Inspector URL and connect `Mailbox` for the orchestrator.
