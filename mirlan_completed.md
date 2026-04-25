# Mirlan — Delegates & Verification: Completed Work

**Role:** Delegates & Verification Lead
**Project:** StandIn Agent Network — LA Hacks 2026
**Date:** 2026-04-25

---

## What Was Built

### 4 Production-Ready Agents

| Agent | Port | File |
|---|---|---|
| Status Agent | 8007 | `agents/status_agent/agent.py` |
| Perform Action Agent | 8008 | `agents/perform_action/agent.py` |
| Historical Agent | 8009 | `agents/historical_agent/agent.py` |
| Watchdog Agent | 8010 | `agents/watchdog_agent/agent.py` |

---

## Task Breakdown

### 1. Seeded Company Data (`data/company_data.py`)

Built the full fictional company dataset for **NovaLoop** demo scenario:

- **USERS** — 5 team members across Engineering, Design, GTM, Product (alice.chen, derek.vasquez, priya.mehta, sam.okafor, kai.torres)
- **SLACK** — 5 messages across `#engineering`, `#design`, `#gtm`, `#general` channels
- **JIRA** — 5 tickets: NOVA-140 through NOVA-144
- **CALENDAR** — 3 meetings (go/no-go, launch sync, engineering standup)
- **Seeded conflict** (intentional, for demo): Design reports `status: ready` ("Launch page is final"), Engineering reports `status: blocked` (NOVA-142 — checkout endpoint changed `/v1/checkout` → `/v2/checkout` overnight). This conflict fires `escalation_required: true` reliably.
- **5 sensitive items** for Gemma redaction testing: fake API key in engineering notes, CVE reference, beta user email, unconfirmed pricing, legal-pending language.

---

### 2. Status Agent (`agents/status_agent/agent.py`) — Port 8007

Single agent replacing 4 delegates + info_collector + verifier in one hop.

**Handles two message types:**
- `FullBriefRequest` → `FullBriefResponse` — full pipeline
- `VerifyRequest` → `VerifyResponse` — standalone verification of pre-collected reports

**Four-phase pipeline:**

| Phase | What it does |
|---|---|
| Phase 1 — Gather | Parallel per-role tool queries: Slack stubs, Jira stubs, seed doc search (all 3 run concurrently via `asyncio.gather`) |
| Phase 2 — Synthesise | Parallel Gemini `gemini-2.0-flash` synthesis per role. Falls back to hardcoded seeded data if Gemini not configured. |
| Phase 3 — Contradict | Rule engine (always fires) + optional Gemini enrichment. Rules are authoritative on `escalation_required` — Gemini cannot override. |
| Phase 4 — Passports | Evidence Passport generated for every high-risk or contradicted claim. |

**Tool stubs (ready for MCP connection):**
- `_tool_slack_search` → `mcp__claude_ai_Slack__slack_search_public_and_private`
- `_tool_jira_search` → `mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql`
- `_tool_rag_query` → local seed doc keyword search (live, no setup needed)
- `_tool_google_drive_search` → `mcp__claude_ai_Google_Drive` (stub)
- `_tool_notion_search` → `mcp__claude_ai_Notion__notion-search` (stub)
- `_tool_web_search` → `WebSearch` (stub)

**Contradiction detection rules:**
- Rule 1: any `ready` role + any `blocked` role → contradiction + escalation
- Rule 2: high-risk claim with no source IDs → unsupported claim flag
- Rule 3: Engineering `blocked` alone → escalation (belt + suspenders)
- Seeded scenario triggers: "Schedule 15-minute escalation with Design and Engineering only."

**Seeded fallbacks** (demo works with zero API keys):
- Engineering: 3 HIGH-risk claims, 2 blockers, `status: blocked`
- Design: 2 LOW-risk claims, 0 blockers, `status: ready`
- GTM: 3 MEDIUM-risk claims, 1 blocker, `status: in_review`
- Product: 4 claims (HIGH/MEDIUM/LOW), 3 blockers, `status: blocked`

**Confidence scoring:** weighted by risk tier (high=1.0×, medium=0.8×, low=0.6×)

**Stale detection:** claims sourced from docs older than 48 h flagged automatically.

---

### 3. Perform Action Agent (`agents/perform_action/agent.py`) — Port 8008

Executes actions on behalf of the orchestrator or escalation agent.

**8 action handlers:**

| Action | Status | MCP when connected |
|---|---|---|
| `send_email` | STUB | `mcp__claude_ai_Gmail` / Microsoft 365 |
| `send_slack` | STUB | `mcp__claude_ai_Slack__slack_send_message` |
| `draft_slack` | STUB | `mcp__claude_ai_Slack__slack_send_message_draft` |
| `create_jira` | STUB | `mcp__claude_ai_Atlassian__createJiraIssue` |
| `update_jira_status` | STUB | `mcp__claude_ai_Atlassian__transitionJiraIssue` |
| `schedule_meeting` | STUB | `mcp__claude_ai_Google_Calendar` |
| `create_action_item` | **LIVE** (needs `MONGODB_URI`) | writes to `standin.action_items` |
| `post_brief` | **LIVE** (needs `MONGODB_URI`) | writes to `standin.evidence_passports` |

- All actions log to `standin.action_log` (fire-and-forget, never crashes main flow)
- Stub actions return structured confirmation so the orchestrator can proceed without blocking
- `stub: true/false` flag in every response so callers know what's real

---

### 4. Historical Agent (`agents/historical_agent/agent.py`) — Port 8009

Answers historical questions about meetings, decisions, and org documents.

**Three-tier retrieval (automatic fallback):**

| Tier | Method | Requires |
|---|---|---|
| 1 | MongoDB Atlas Vector Search (`$vectorSearch`, cosine similarity, 768-dim) | `MONGODB_URI` + `GEMINI_API_KEY` + vector index |
| 2 | Keyword search over full 25-doc corpus (BM25-style, title hits weighted 2×) | Nothing — always available |
| 3 | Gemini synthesis with no context | `GEMINI_API_KEY` |

**Corpus coverage (Tier 2):** all 25 documents — 12 seed JSON files + 5 Slack messages + 5 Jira tickets + 3 calendar events. Fixed from initial version which only covered 12 files.

**Confidence scoring:** 0.85 base (vector) / 0.65 (keyword), +0.02 per doc returned, capped at 0.95.

**Supports `role_filter`** — restrict results to Engineering, Design, GTM, or Product documents.

---

### 5. Seed Data Files (`data/seed/`) — 12 JSON documents

| File | Type | Role | Sensitive |
|---|---|---|---|
| `api_contract_change.json` | engineering_doc | Engineering | — |
| `backend_ticket.json` | jira_ticket | Engineering | — |
| `beta_feedback.json` | feedback_report | Product | NPS data + beta user email |
| `design_asset_note.json` | design_doc | Design | — |
| `design_slack.json` | slack_export | Design | — |
| `engineering_notes.json` | internal_notes | Engineering | Fake API key (`sk-prod-abc123xyz`) |
| `go_no_go.json` | decision_doc | Product | — |
| `gtm_notes.json` | gtm_doc | GTM | Unconfirmed pricing (CONFIDENTIAL) |
| `incident_risk.json` | incident_report | Engineering | CVE-2024-38112 reference |
| `launch_brief.json` | brief | Product | Legal-pending language |
| `launch_readiness.json` | status_report | Product | — |
| `qa_bug_report.json` | bug_report | Engineering | — |

---

### 6. MongoDB Seeder (`data/seed_db.py`)

Run once: `python data/seed_db.py`

- Upserts all 25 documents into `standin.documents`
- Generates Gemini `text-embedding-004` embeddings (768-dim) when `GEMINI_API_KEY` set
- Upserts 5 user profiles into `standin.agent_profiles`
- Upserts 3 calendar events into `standin.meetings`
- Attempts programmatic Atlas vector index creation; prints manual UI instructions if unavailable

**Vector index definition:**
```json
{
  "name": "standin_vector_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      { "type": "vector", "path": "embedding", "numDimensions": 768, "similarity": "cosine" },
      { "type": "filter", "path": "role" },
      { "type": "filter", "path": "source" }
    ]
  }
}
```

---

### 7. Shared Models (`models.py`)

All uAgents message models for the network. Key models:

| Model | Used by |
|---|---|
| `FullBriefRequest / FullBriefResponse` | Orchestrator ↔ Status Agent |
| `VerifyRequest / VerifyResponse` | Orchestrator ↔ Status Agent (standalone verify) |
| `RAGRequest / RAGResponse` | Any agent ↔ Historical Agent |
| `ActionRequest / ActionResponse` | Orchestrator ↔ Perform Action Agent |
| `Claim` | Nested in MeetingResponse — single sourced fact |
| `EvidencePassport` | Output of verification — claim provenance record |
| `MeetingResponse` | Per-role status report (embedded in FullBriefResponse) |

---

## MongoDB Collections

| Collection | Purpose | Live? |
|---|---|---|
| `standin.documents` | RAG corpus — 25 docs + embeddings | Needs `MONGODB_URI` + seed run |
| `standin.agent_profiles` | User/agent identity records | Needs `MONGODB_URI` + seed run |
| `standin.meetings` | Calendar event records | Needs `MONGODB_URI` + seed run |
| `standin.action_items` | Action items from perform_action | Live when `MONGODB_URI` set |
| `standin.evidence_passports` | Brief results from perform_action | Live when `MONGODB_URI` set |
| `standin.action_log` | Audit log of every action | Live when `MONGODB_URI` set |

---

## What Still Needs to Be Done

| Item | Owner | Notes |
|---|---|---|
| Add `MONGODB_URI` + `GEMINI_API_KEY` + `ELEVENLABS_API_KEY` to `.env` | Mirlan | Required to activate Tier 1 RAG, seeder, live actions |
| Run `python data/seed_db.py` | Mirlan | Seeds MongoDB; then create vector index in Atlas UI |
| Create Atlas vector search index | Mirlan | Seed script prints exact JSON — paste into Atlas UI |
| Orchestrator agent | Tomiwa | Entry point that calls status_agent + historical_agent + perform_action |
| Fill in `AGENT_ADDRESSES` in `data/company_data.py` | Both | After Agentverse deployment of each agent |
| ElevenLabs Brief Narrator (port 8010) | Mirlan | Spoken 30-second brief — "do not cut" item per spec |
| Connect MCP tools (Slack, Jira, Drive, Calendar) | Both | Stubs are labeled with exact MCP names to swap in |

---

## How to Run

```bash
# Activate venv (Windows)
.venv\Scripts\activate

# Seed MongoDB (once)
python data/seed_db.py

# Start agents (separate terminals)
python agents/status_agent/agent.py    # port 8007
python agents/perform_action/agent.py   # port 8008
python agents/historical_agent/agent.py         # port 8009
```

Required `.env`:
```
ASI_ONE_API_KEY=...
MONGODB_URI=mongodb+srv://...
GEMINI_API_KEY=...
ELEVENLABS_API_KEY=...
```
