# StandIn Orchestrator

StandIn Orchestrator is the public-facing coordination agent for the StandIn multi-agent system.

It accepts `AgentChatProtocol v0.3.0` chat messages, classifies the request, routes it to the right internal worker, and returns a concise response back to the user. The orchestrator is the only agent intended to be exposed through Agentverse / ASI:One. All other agents stay private behind it.

## What This Agent Does

- Answers current status and launch-readiness questions
- Compares team narratives to surface contradictions or blockers
- Retrieves past decisions, prior context, and document-backed history
- Triggers actions such as creating Jira tickets, drafting or sending Slack updates, scheduling meetings, and creating action items
- Produces cross-functional briefings across Engineering, Design, GTM, and Product

## How Routing Works

The orchestrator classifies each incoming request into one of five intents:

- `status_query`
- `conflict_check`
- `history_query`
- `action_request`
- `briefing_request`

It then dispatches the request to the appropriate internal agent:

- `status_agent` for live status, launch readiness, contradiction checks, and executive briefs
- `historical_agent` for RAG-based lookups across seeded documents, Slack, Jira, and calendar history
- `perform_action` for operational tasks such as Jira, Slack, calendar, and action-item flows

## Best-Fit Use Cases

- "What is blocking Launch Alpha right now?"
- "Are Engineering and Design aligned on checkout readiness?"
- "What was decided in the earlier pricing discussion?"
- "Create a Jira ticket for the checkout API v2 blocker."
- "Give me a product-level briefing across all teams."

## Example Prompts

- `Give me a briefing on Launch Alpha readiness.`
- `Check whether Product and Engineering are contradicting each other on the launch timeline.`
- `What happened in the last pricing review meeting?`
- `Create a Jira ticket for the checkout API v2 blocker and mark it Medium priority.`
- `Draft a Slack update for #standin-updates summarizing the current blockers.`

## Response Behavior

- Status and briefing requests return structured summaries with role-level blockers and an overall confidence score.
- History requests return an answer, supporting source IDs, and the retrieval method used.
- Action requests return either an execution result or a pending approval message when human approval is required.
- Empty or unclear messages are rejected instead of being guessed.

## Data Modes

StandIn currently supports two operating modes:

- `live`: Gemini-backed synthesis using connected services where available
- `seeded`: fallback mode using local demo data and stubbed integrations

If `GEMINI_API_KEY` is not configured, or downstream services are unavailable, the orchestrator still works by falling back to seeded behavior. This makes it suitable for local demos, but some answers and actions may be simulated rather than executed live.

## Current Action Coverage

Requests may be routed into the action pipeline for:

- `create_jira`
- `update_jira_status`
- `send_slack`
- `draft_slack`
- `send_email`
- `schedule_meeting`
- `create_action_item`
- `post_brief`

Some actions execute immediately, some require approval, and some may run in stub mode depending on configured services and environment variables.

## Protocols

- `AgentChatProtocol v0.3.0`
  - `ChatMessage`
  - `ChatAcknowledgement`

## Local Development

Start the full local topology from the repository root:

```powershell
.\.venv\Scripts\python backend\main.py
```

Run a one-shot orchestrator test:

```powershell
.\.venv\Scripts\python backend\test_orchestrator.py "Create a Jira ticket for the checkout API v2 blocker."
```

## Configuration

Important environment variables:

- `AGENTVERSE_SEED`
- `ORCHESTRATOR_PORT`
- `ORCHESTRATOR_ENDPOINT`
- `STATUS_AGENT_ADDRESS`
- `HISTORICAL_AGENT_ADDRESS`
- `PERFORM_ACTION_ADDRESS`
- `GEMINI_API_KEY`
- `MONGODB_URI`

## Notes

- Only the orchestrator should be listed publicly.
- Internal worker agents are implementation details and are not intended for direct user interaction.
- This agent is optimized for cross-functional coordination workflows rather than open-ended general chat.
