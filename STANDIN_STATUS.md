# StandIn — Project Status
**LA Hacks 2026 | Last updated: 2026-04-25**

> Stop attending meetings for information. Send your StandIn.

---

## Team & Ownership

| Area | Owner | Status |
|---|---|---|
| Orchestrator Agent | Tomiwa | In progress |
| Status Agent + Verification | Mirlan | Done |
| Perform Action Agent | Mirlan | Done |
| Historical Agent (RAG) | Mirlan | Done |
| Watchdog Agent | Mirlan | Done |
| Dashboard Graph API | Mirlan | Done |
| MCP Tool Connections (Slack, Jira, etc.) | TBD | Stub — ready to connect |
| Voice Brief (ElevenLabs) | TBD | Not started |
| Dashboard UI | TBD | Not started |
| Agentverse Registration | All | Not started |

---

## Agent Network

| Agent | Port | File | Handles |
|---|---|---|---|
| Orchestrator | 8000 | `backend/agents/orchestrator_agent.py` | Entry point — routes to sub-agents |
| Status Agent | 8007 | `backend/agents/status_agent/agent.py` | Current status briefs + verification |
| Perform Action | 8008 | `backend/agents/perform_action/agent.py` | Actions + approval gate + graph API |
| Historical Agent | 8009 | `backend/agents/historical_agent/agent.py` | RAG — historical Q&A |
| Watchdog Agent | 8010 | `backend/agents/watchdog_agent/agent.py` | Proactive monitoring + alerts |

### How to run
```bash
.venv\Scripts\activate
python backend/agents/status_agent/agent.py        # port 8007
python backend/agents/perform_action/agent.py      # port 8008
python backend/agents/historical_agent/agent.py    # port 8009
python backend/agents/watchdog_agent/agent.py      # port 8010
# Tomiwa's orchestrator:
python backend/agents/orchestrator_agent.py        # port 8000
```

---

## Message Flow

```
User / ASI:One
      ↓  (Chat Protocol)
Orchestrator (8000)  ←── Tomiwa
      ├── FullBriefRequest  ──→  Status Agent (8007)
      │                              └── FullBriefResponse (roles, contradictions, passports)
      ├── RAGRequest  ──────────→  Historical Agent (8009)
      │                              └── RAGResponse (answer, sources, confidence)
      └── ActionRequest  ───────→  Perform Action (8008)
                                       └── ActionResponse (success, pending_approval, stub)

Watchdog (8010)  ──→  Status Agent (poll every 30 min)
                └── on change ──→  Perform Action (draft_slack alert)
```

---

## MongoDB Collections

| Collection | Purpose | Seeded? | Live writes? |
|---|---|---|---|
| `standin.documents` | RAG corpus — 25 docs + embeddings | Yes (`seed_db.py`) | No |
| `standin.agent_profiles` | User/agent identity | Yes | No |
| `standin.meetings` | Calendar events | Yes | No |
| `standin.interactions` | Graph edges (Slack, Jira, meetings) | Yes | No |
| `standin.brief_history` | Conversation memory per user | No | Yes — status_agent |
| `standin.action_items` | Action items created by agents | No | Yes — perform_action |
| `standin.evidence_passports` | Stored briefs | No | Yes — perform_action |
| `standin.pending_approvals` | Actions awaiting human approval | No | Yes — perform_action |
| `standin.action_log` | Audit log of all actions | No | Yes — perform_action |
| `standin.watchdog_snapshots` | Periodic status snapshots | No | Yes — watchdog |

### Seed the database
```bash
python backend/data/seed_db.py
```
Requires `MONGODB_URI` and optionally `GEMINI_API_KEY` in `.env`.

---

## REST Endpoints (perform_action, port 8008)

All endpoints available when `python agents/perform_action/agent.py` is running.

| Method | Path | Description | Auth needed? |
|---|---|---|---|
| `GET` | `/graph` | User interaction graph for dashboard UI | No |
| `GET` | `/approvals` | List all pending human approvals | No |
| `POST` | `/approvals/approve` | Approve + execute a pending action | No |
| `POST` | `/approvals/reject` | Reject a pending action | No |

### GET /graph — response shape
```json
{
  "nodes": [
    { "id": "alice.chen", "name": "Alice Chen", "role": "Product Manager",
      "team": "Product", "email": "alice.chen@novaloop.io", "agent_slug": "" }
  ],
  "edges": [
    { "from_user": "alice.chen", "to_user": "derek.vasquez",
      "type": "meeting", "source_id": "launch_sync_001",
      "label": "Launch Alpha — Go/No-Go Sync",
      "timestamp": "2026-04-28T09:00:00Z", "weight": 1 }
  ],
  "generated_at": "2026-04-25T10:00:00Z",
  "source": "mongodb"
}
```
`source` is `"mongodb"` when seeded, `"hardcoded"` when MONGODB_URI not set.

Edge `type` values: `"meeting"` | `"slack_thread"` | `"jira"`

---

## Key Models (`models.py`)

| Model | Direction | Purpose |
|---|---|---|
| `FullBriefRequest` | Orchestrator → Status Agent | Request brief; include `session_id` to resume conversation |
| `FullBriefResponse` | Status Agent → Orchestrator | Roles + contradictions + passports + `delta_claims` |
| `VerifyRequest` | Any → Status Agent | Standalone verification of pre-collected responses |
| `VerifyResponse` | Status Agent → Any | Contradictions + evidence passports |
| `RAGRequest` | Any → Historical Agent | Historical question + optional role_filter |
| `RAGResponse` | Historical Agent → Any | Answer + source IDs + confidence |
| `ActionRequest` | Any → Perform Action | Action type + JSON payload |
| `ActionResponse` | Perform Action → Any | Success + result (or `pending_approval` message) |
| `GraphNode` | — | Dashboard user node |
| `GraphEdge` | — | Dashboard interaction edge |
| `GraphResponse` | — | Full graph payload from `GET /graph` |
| `WatchdogAlert` | Watchdog internal | Change description sent to perform_action |
| `ApproveRequest/Response` | REST → Perform Action | Approve a pending action |
| `RejectRequest/Response` | REST → Perform Action | Reject a pending action |

---

## Human Approval Gate

Actions that **require human approval** before executing (when `MONGODB_URI` set):
- `send_email`
- `send_slack`
- `schedule_meeting`

Actions that **execute immediately**:
- `draft_slack` (creates a draft, already approval-style)
- `create_jira`
- `update_jira_status`
- `create_action_item`
- `post_brief`

**Flow:**
1. Agent sends `ActionRequest` for `send_email`
2. Perform Action saves to `standin.pending_approvals`, returns `pending_approval` response
3. Human calls `POST /approvals/approve` with the `action_id`
4. Perform Action executes the action and logs the result

---

## What's Hardcoded vs Real

| Feature | Current state | Replaced when |
|---|---|---|
| Slack data | `data/company_data.py` SLACK dict | `mcp__claude_ai_Slack__slack_search_public_and_private` connected |
| Jira data | `data/company_data.py` JIRA dict | `mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql` connected |
| Google Drive | Returns empty list | `mcp__claude_ai_Google_Drive` connected |
| Notion | Returns empty list | `mcp__claude_ai_Notion__notion-search` connected |
| Web search | Returns empty list | `WebSearch` connected |
| Email send | Stub confirmation | `mcp__claude_ai_Gmail` connected + approval gate |
| Slack send | Stub confirmation | `mcp__claude_ai_Slack__slack_send_message` + approval gate |
| Calendar create | Stub confirmation | `mcp__claude_ai_Google_Calendar` + approval gate |
| Jira create | Stub confirmation | `mcp__claude_ai_Atlassian__createJiraIssue` connected |
| RAG embeddings | Keyword fallback | `GEMINI_API_KEY` + `seed_db.py` + Atlas vector index |

Each stub in `status_agent` and `perform_action` has a comment with the exact MCP tool name to swap in.

---

## Seeded Demo Scenario

Company: **NovaLoop** — Checkout AI Assistant, Launch Alpha, deadline Monday 2026-04-28.

**Intentional conflict (always fires for demo):**
- Design says: *"Launch page is final and ready to ship"* → `status: ready`
- Engineering says: *"NOVA-142 blocked — checkout API changed /v1→/v2 last night"* → `status: blocked`

**Expected output:**
```
escalation_required: true
escalation_reason: "Design reports launch page ready. Engineering reports checkout
                    integration blocked (NOVA-142). These claims directly conflict."
recommended_action: "Schedule 15-minute escalation with Design and Engineering only."
```

**5 sensitive items** in seed docs (for redaction testing):
- `engineering_notes.json` — fake API key (`sk-prod-abc123xyz`)
- `beta_feedback.json` — beta user email
- `incident_risk.json` — CVE-2024-38112 reference
- `gtm_notes.json` — CONFIDENTIAL pricing
- `launch_brief.json` — legal-pending language

---

## Required `.env`

```
ASI_ONE_API_KEY=...          # already set
MONGODB_URI=...              # needed for DB features
GEMINI_API_KEY=...           # needed for Tier 1 RAG + synthesis
ELEVENLABS_API_KEY=...       # needed for voice brief (not built yet)

# Agent seeds (keep stable — changing seed = new Agentverse address)
ORCHESTRATOR_SEED=...
STATUS_AGENT_SEED=status_agent_standin_seed_v1
PERFORM_ACTION_SEED=perform_action_standin_seed_v1
HISTORICAL_AGENT_SEED=historical_agent_standin_seed_v1
WATCHDOG_SEED=watchdog_standin_seed_v1

# Agent addresses (fill after each agent starts — printed in startup log)
STATUS_AGENT_ADDRESS=agent1q...
PERFORM_ACTION_ADDRESS=agent1q...
HISTORICAL_AGENT_ADDRESS=agent1q...
WATCHDOG_ADDRESS=agent1q...
```

---

## Agentverse Registration

All agents have `mailbox=True` and `publish_agent_details=True` — they self-register when started.

**For the demo/ASI:One listing:** Only the Orchestrator address needs to be in the marketplace. Sub-agent addresses are private and go in `.env`.

Steps per agent:
1. Start the agent — it prints its address in the startup log
2. Copy the `agent1q...` address into `.env` under the matching `*_ADDRESS` variable
3. For the Orchestrator only: register in the ASI:One marketplace listing

---

## What Still Needs to Be Built

| Item | Priority | Notes |
|---|---|---|
| Orchestrator agent | Critical | Tomiwa — routes between status/historical/perform_action |
| Agentverse registration | Critical | Run each agent, copy addresses to `.env` |
| MongoDB + Gemini keys in `.env` | Critical | Mirlan — activate all DB features |
| Atlas vector index | High | After `seed_db.py` — paste JSON into Atlas UI |
| ElevenLabs voice brief | High | "Do not cut" per spec — 30-second spoken brief |
| MCP tool connections | Medium | Swap stubs when tools are connected |
| Dashboard UI | Medium | Other teammate — `GET /graph` endpoint ready |
| Escalation Agent | Medium | Receives passport, decides action, calls perform_action |
