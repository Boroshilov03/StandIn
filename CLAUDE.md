# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project

**StandIn Agent Network** — LA Hacks 2026 hackathon project.

> Stop attending meetings for information. Send your StandIn.

A network of AI agents that gather status from data sources (Slack, Jira, Calendar), detect contradictions across teams, answer historical questions, and execute actions — all coordinated through Fetch.ai Agentverse and exposed via ASI:One.

---

## System Boundaries

### Cloud boundary
All agents, orchestrator, MongoDB Atlas, and the RAG engine run in the cloud. Users interact via ASI:One.

### On-premise boundary (ASUS GX10) — stretch goal
Local edge device acting as a mandatory privacy gateway. Raw data from Slack/Gmail/Calendar passes through the GX10 first for PII classification and redaction before reaching MongoDB. Nothing sensitive ever hits the cloud directly. **Not yet built — cut if time is tight.**

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Agent framework | Fetch.ai uAgents 0.22.5 | Agent registration, Chat Protocol, message passing |
| Agent marketplace | Agentverse (Fetch.ai) | Discovery, hosted mailboxes |
| Chat interface | ASI:One | User-facing entry point (no custom frontend) |
| LLM — cloud | Google Gemini `gemini-2.5-flash` | Intent extraction, synthesis, conflict detection, structured output |
| LLM — local privacy filter | Model on ASUS GX10 | PII classification + redaction (stretch) |
| Embeddings | Gemini `text-embedding-004` (768-dim) | RAG vector search |
| Database | MongoDB Atlas | All persistent state |
| Vector search | MongoDB Atlas Vector Search | RAG Tier 1 retrieval |
| Voice | ElevenLabs | Spoken 30-second executive brief — do not cut |
| External APIs | Slack, Jira, Google Calendar, Gmail | Live integrations — currently stubbed |

---

## Environment Setup

Python 3.11, local venv. No formal packaging.

```bash
.venv\Scripts\activate          # Windows — activate before running anything
pip install uagents==0.22.5 uagents-adapter==0.4.0 google-generativeai pymongo python-dotenv elevenlabs langchain==0.3.23 langgraph==0.3.20 langchain-openai==0.2.14
```

Use exact versions — `uagents==0.22.5` is the tested-compatible release.

Required `.env` variables:
```
ASI_ONE_API_KEY=

MONGODB_URI=
GEMINI_API_KEY=
ELEVENLABS_API_KEY=

# Agent seeds — keep stable, changing seed = new Agentverse address
ORCHESTRATOR_SEED=
STATUS_AGENT_SEED=status_agent_standin_seed_v1
PERFORM_ACTION_SEED=perform_action_standin_seed_v1
HISTORICAL_AGENT_SEED=historical_agent_standin_seed_v1
WATCHDOG_SEED=watchdog_standin_seed_v1

# Agent addresses — fill after each agent starts (printed in startup log)
STATUS_AGENT_ADDRESS=agent1q...
PERFORM_ACTION_ADDRESS=agent1q...
HISTORICAL_AGENT_ADDRESS=agent1q...
WATCHDOG_ADDRESS=agent1q...
```

---

## Agent Architecture

The Orchestrator is the ASI:One-facing entrypoint. For local testing, run the full topology through `backend/main.py`; for hosted setups, publish the orchestrator and keep downstream agent wiring explicit in configuration.

| Agent | Port | File | Status | Owner |
|---|---|---|---|---|
| Orchestrator | 8000 | `backend/agents/orchestrator/agent.py` | Implemented locally | Tomiwa |
| Status Agent | 8007 | `backend/agents/status_agent/agent.py` | Done | Mirlan |
| Perform Action | 8008 | `backend/agents/perform_action/agent.py` | Done | Mirlan |
| Historical Agent | 8009 | `backend/agents/historical_agent/agent.py` | Done | Mirlan |
| Watchdog Agent | 8010 | `backend/agents/watchdog_agent/agent.py` | Done | Mirlan |

### Orchestrator — intent classification

The Orchestrator uses Gemini to classify every incoming user message into one of five intents before routing:

| Intent | Name | Routes to | Example |
|---|---|---|---|
| 1 | Status query | Status Agent | "What is engineering working on?" |
| 2 | Conflict check | Status Agent | "Is GTM aligned with engineering on the launch date?" |
| 3 | Action request | Perform Action | "Schedule a call between Alice and Carol" |
| 4 | History query | Historical Agent | "What was decided in last week's launch sync?" |
| 5 | Briefing request | Status Agent | "Give me a morning brief" |

Gemini extracts: `intent_type`, `teams`, `topic`, `time_window`, `action_type`, `parties`.

### Status Agent (port 8007)

Handles intents 1, 2, 5 via a four-phase pipeline:

1. **Gather** — parallel async tool queries per role (Slack stubs, Jira stubs, local RAG keyword search)
2. **Synthesise** — parallel Gemini synthesis per role; falls back to seeded hardcoded data if Gemini not configured
3. **Contradict** — rule engine (always fires) + optional Gemini enrichment. Rules are authoritative on `escalation_required` — Gemini cannot override.
4. **Passports** — Evidence Passport generated for every high-risk or contradicted claim

Also handles `VerifyRequest` → `VerifyResponse` for standalone verification of pre-collected role reports.

Stores per-user conversation history in `standin.brief_history`. Detects deltas (status changes, new blockers, confidence drops >0.10) on repeated calls for the same user.

### Historical Agent (port 8009)

Handles intent 4 (history queries). Three-tier retrieval with automatic fallback:

| Tier | Method | Requires |
|---|---|---|
| 1 | MongoDB Atlas Vector Search (768-dim cosine) | `MONGODB_URI` + `GEMINI_API_KEY` + vector index |
| 2 | BM25-style keyword search over all 25 docs | Nothing — always available |
| 3 | Gemini synthesis with no context | `GEMINI_API_KEY` |

Corpus: 12 seed JSON files + 5 Slack messages + 5 Jira tickets + 3 Calendar events = 25 docs total.

### Perform Action Agent (port 8008)

Handles intent 3. Executes 8 action types:

| Action | Approval required? | Status |
|---|---|---|
| `send_email` | Yes | Stub → `mcp__claude_ai_Gmail` |
| `send_slack` | Yes | Stub → `mcp__claude_ai_Slack__slack_send_message` |
| `schedule_meeting` | Yes | Stub → `mcp__claude_ai_Google_Calendar` |
| `draft_slack` | No | Stub → `mcp__claude_ai_Slack__slack_send_message_draft` |
| `create_jira` | No | Stub → `mcp__claude_ai_Atlassian__createJiraIssue` |
| `update_jira_status` | No | Stub → `mcp__claude_ai_Atlassian__transitionJiraIssue` |
| `create_action_item` | No | Live — writes to `standin.action_items` |
| `post_brief` | No | Live — writes to `standin.evidence_passports` |

Approval-required actions are saved to `standin.pending_approvals` and return a `pending_approval` response immediately. Humans call REST endpoints to approve/reject.

REST endpoints (all on port 8008):
- `GET /graph` — user interaction graph for dashboard UI
- `GET /approvals` — list pending human approvals
- `POST /approvals/approve` — approve + execute a pending action
- `POST /approvals/reject` — reject a pending action

### Watchdog Agent (port 8010)

Polls Status Agent every 30 minutes (`WATCHDOG_INTERVAL_SECONDS` env override). On change, sends a `draft_slack` alert via Perform Action. Stores snapshots in `standin.watchdog_snapshots`.

---

## Message Flow

```
User / ASI:One
      ↓  (Chat Protocol)
Orchestrator (8000)
      ├── FullBriefRequest  ──→  Status Agent (8007)
      │                              └── FullBriefResponse
      ├── RAGRequest  ──────────→  Historical Agent (8009)
      │                              └── RAGResponse
      └── ActionRequest  ───────→  Perform Action (8008)
                                       └── ActionResponse

Watchdog (8010)  ──→  Status Agent (poll every 30 min)
                └── on change ──→  Perform Action (draft_slack)
```

---

## MongoDB Collections (database: `standin`)

| Collection | Purpose | Seeded? | Live writes? |
|---|---|---|---|
| `documents` | RAG corpus — 25 docs + embeddings | Yes (`seed_db.py`) | No |
| `agent_profiles` | User/agent identity | Yes | No |
| `meetings` | Calendar events | Yes | No |
| `interactions` | Graph edges (Slack, Jira, meetings) | Yes | No |
| `brief_history` | Conversation memory per user | No | Yes — status_agent |
| `action_items` | Action items from perform_action | No | Yes — perform_action |
| `evidence_passports` | Stored briefs | No | Yes — perform_action |
| `pending_approvals` | Actions awaiting human approval | No | Yes — perform_action |
| `action_log` | Audit log of all actions | No | Yes — perform_action |
| `watchdog_snapshots` | Periodic status snapshots | No | Yes — watchdog |

Seed the database:
```bash
python backend/data/seed_db.py
```
Requires `MONGODB_URI` in `.env` (`.env` lives at project root). Gemini embeddings generated when `GEMINI_API_KEY` set.

After seeding, create the Atlas Vector Search index manually in Atlas UI (seed_db.py prints exact JSON).

---

## Evidence Passport

Every Status Agent output includes an Evidence Passport per claim. This is the core feature that distinguishes StandIn from a generic chatbot wrapper.

```json
{
  "claim": "...",
  "source": "...",
  "owner": "...",
  "timestamp": "...",
  "confidence": "high|medium|low",
  "contradictions": ["..."],
  "recommended_action": "...",
  "escalation_required": true
}
```

---

## Seeded Demo Scenario

Company: **NovaLoop** — Checkout AI Assistant, Launch Alpha, deadline Monday 2026-04-28.

**Intentional conflict (always fires):**
- Design: "Launch page is final and ready to ship" → `status: ready`
- Engineering: "NOVA-142 blocked — checkout API changed /v1→/v2 last night" → `status: blocked`

Expected output: `escalation_required: true`, "Schedule 15-minute escalation with Design and Engineering only."

Five sensitive items in seed docs for redaction testing: fake API key, CVE reference, beta user email, confidential pricing, legal-pending language.

---

## Running

```bash
.venv\Scripts\activate

# Seed MongoDB (once — run from project root)
python backend/data/seed_db.py

# Start the local topology (run from project root)
python backend/main.py

# One-shot orchestrator routing test
python backend/test_orchestrator.py "Give me a briefing on Launch Alpha readiness."
```

Exploration scripts:
```bash
python backend/asii_test.py       # ASI.1 API smoke test
python backend/interval_task.py   # Minimal uagents hello-world reference
```

---

## File Structure (current)

```
standin/
├── backend/
│   ├── agents/
???   ???   ????????? orchestrator/
???   ???   ???   ????????? agent.py                # Intent classification + routing (Tomiwa)
│   │   ├── status_agent/
│   │   │   └── agent.py                # Gather + synthesise + contradict + passports (port 8007)
│   │   ├── perform_action/
│   │   │   └── agent.py                # Actions + approval gate + graph API (port 8008)
│   │   ├── historical_agent/
│   │   │   └── agent.py                # RAG — historical Q&A (port 8009)
│   │   └── watchdog_agent/
│   │       └── agent.py                # Proactive monitoring + alerts (port 8010)
│   ├── data/
│   │   ├── company_data.py             # Seeded NovaLoop company data (USERS, SLACK, JIRA, CALENDAR)
│   │   ├── seed_db.py                  # MongoDB seeder + embedding generator
│   │   └── seed/                       # 12 JSON seed documents
???   ????????? models.py                       # All shared uAgents message models
│   ├── asii_test.py                    # ASI.1 API smoke test
│   └── interval_task.py                # uagents hello-world reference
├── frontend/                           # (empty — UI to be built)
├── .env                                # API keys — stays at project root
└── CLAUDE.md
```

---

## What Still Needs to Be Built

| Item | Priority | Owner |
|---|---|---|
| Orchestrator agent | Critical | Tomiwa |
| Agentverse registration — run agents, copy addresses to `.env` | Critical | All |
| Add `MONGODB_URI` + `GEMINI_API_KEY` + `ELEVENLABS_API_KEY` to `.env` | Critical | Mirlan |
| Run `seed_db.py`, create Atlas vector index | High | Mirlan |
| ElevenLabs voice brief (spoken 30-second brief) | High | TBD — do not cut |
| Connect MCP tools (Slack, Jira, Drive, Calendar) | Medium | TBD |
| Dashboard UI (graph view) | Medium | TBD — `GET /graph` endpoint ready |
| ASUS GX10 local privacy filter | Stretch | — |

---

## uAgents Code Rules

**Models** — always use `uagents.Model`, never `pydantic.BaseModel`. Never use `@field_validator` (causes pickle errors in message passing).

**Timestamps** — use `datetime.now(UTC)`, never `datetime.utcnow()`.

**REST endpoints** — GET handlers take only `ctx`; POST handlers take `ctx` + request model. Signatures must match exactly or the agent fails silently.

**Agent communication** — agents run in separate terminals. Start the listener first, copy its printed address, paste into the initiator. Never use placeholder addresses.

**LangGraph** — use the simple function wrapper (`chat_agent_executor.create_tool_calling_executor`). Do not build multi-node `StateGraph` pipelines for tasks that fit in a single function call.

**Agent identity** — `seed` must come from an env var in any non-throwaway code. The seed determines the Agentverse address; changing it creates a different agent.

**Agentverse deployment** — for hosted agents, remove `port` and `endpoint` from `Agent()`; Agentverse provides these. For local/hybrid, keep them and set `mailbox=True`.

**Async Gemini** — use `client.aio.models.generate_content` inside async handlers, not the sync version.

---

## Slash Commands

- `/new-agent <role>` — Scaffolds a new StandIn agent file with Agentverse registration, Chat Protocol, MongoDB, Gemini, and correct uagents patterns.

---

## Registered Agent Addresses

*(Fill in after starting each agent — address is printed in startup log)*

| Agent | Agentverse Address |
|---|---|
| Orchestrator | |
| Status Agent | |
| Perform Action | |
| Historical Agent | |
| Watchdog Agent | |


