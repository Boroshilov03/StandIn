# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project

**StandIn Agent Network** — LA Hacks 2026 hackathon project.

> Stop attending meetings for information. Send your StandIn.

A network of scoped AI delegates that handle low-stakes status exchange, deconfliction, and information gathering. Agents coordinate async, then a Verifier Agent produces an Evidence Passport: what was claimed, what source supports it, who owns it, and whether a human needs to step in.

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
```

Each agent also needs a seed env var (e.g. `ORCHESTRATOR_SEED`, `ENGINEERING_SEED`, etc.) to keep identities stable across restarts.

---

## Running

```bash
python agents/orchestrator_agent.py   # Start orchestrator (port 8000)
python agents/engineering_agent.py    # Start engineering delegate (port 8001)
# etc — each agent runs as its own process
```

Existing exploration scripts:
```bash
python asii_test.py       # One-shot ASI.1 API call — kept as API smoke test
python interval_task.py   # Minimal uagents hello-world reference
```

---

## Agent Architecture

All agents are registered on **Fetch.ai Agentverse** and discoverable via **ASI:One**. Inter-agent communication uses the **Chat Protocol** (`uagents_core.contrib.protocols.chat`).

| Agent | Port | Role |
|---|---|---|
| Orchestrator | 8000 | Entry point — receives user delegation requests, discovers and routes to role agents, assembles final brief |
| Engineering Delegate | 8001 | Represents engineering team state |
| Design Delegate | 8002 | Represents design team state |
| Product Delegate | 8003 | Represents product team state |
| GTM Delegate | 8004 | Represents go-to-market team state |
| Verifier | 8005 | Scans updates for contradictions, stale claims, and low-confidence assertions |
| Escalation | 8006 | Decides async-safe vs. human-required; creates action items |

### Request flow

1. User sends delegation request to Orchestrator via ASI:One.
2. Orchestrator uses Discovery logic to identify relevant role agents.
3. Role agents query MongoDB for current state, then respond with structured updates.
4. Verifier checks claims for contradictions and confidence.
5. Escalation Agent determines if any issue requires a human meeting.
6. Orchestrator assembles the Evidence Passport and returns the brief.
7. (Optional) ElevenLabs generates a 30-second spoken brief.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Agent network | Fetch.ai Agentverse + uagents | Agent registration, discovery, Chat Protocol |
| Reasoning | Google Gemini (`gemini-2.0-flash`) | Function calling, summarization, conflict detection, structured output |
| Memory | MongoDB Atlas | Agent profiles, updates, evidence, action items, meeting history |
| Voice | ElevenLabs | Per-agent voices for demo; spoken executive brief |
| LLM API | ASI.1 (`asi1` model) | Alternative reasoning endpoint via ASI:One |

---

## MongoDB Collections

- `agent_profiles` — role, name, current_projects, communication_style, agentverse_address
- `updates` — agent_id, content, timestamp, confidence, source_links
- `evidence` — claim, source, owner, timestamp, confidence, contradictions
- `action_items` — description, owner, urgency, escalation_required, created_by
- `meetings` — participants, summary, decisions, evidence_passport_id

Seed the database with a simulated company: 4 roles, 1 product launch, ~10 documents/messages/tickets. Real Slack/Drive integrations are out of scope for the MVP.

---

## Evidence Passport

Every Orchestrator output must include an Evidence Passport:

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

This is the feature that distinguishes StandIn from a generic chatbot wrapper.

---

## Build Order

1. Agentverse registration + Chat Protocol working between 2 agents via ASI:One
2. MongoDB seeded + Orchestrator can read/write all collections
3. Gemini function calling for summarization and conflict detection
4. Evidence Passport generation
5. All 5 role agents + Verifier + Escalation wired together
6. ElevenLabs voices for demo agent conversation + spoken brief
7. (Stretch) ASUS GX10 local redaction layer

**Do not cut:** Agentverse registration, ASI:One demo, multi-agent exchange, MongoDB memory, Gemini synthesis, Evidence Passport.

**Cut first if time is tight:** ZETIC mobile app, ASUS hardware layer, real Slack/Drive integrations.

---

## uAgents Code Rules

Full rules live in `.cursor/rules/fetchai.mdc` (Cursor IDE picks these up automatically). Key rules for Claude Code:

**Models** — always use `uagents.Model`, never `pydantic.BaseModel`. Never use `@field_validator` (causes pickle errors in message passing).

**Timestamps** — use `datetime.now(UTC)`, never `datetime.utcnow()`.

**REST endpoints** — GET handlers take only `ctx`; POST handlers take `ctx` + request model. Signatures must match exactly or the agent fails silently.

**Agent communication** — agents run in separate terminals. Start the listener first, copy its printed address, paste into the initiator. Never use placeholder addresses.

**LangGraph** — use the simple function wrapper (`chat_agent_executor.create_tool_calling_executor`). Do not build multi-node `StateGraph` pipelines for tasks that fit in a single function call.

**Agent identity** — `seed` must come from an env var in any non-throwaway code. The seed determines the agent's Agentverse address; changing it creates a different agent.

**Agentverse deployment** — for hosted agents, remove `port` and `endpoint` from the `Agent()` constructor; Agentverse provides these. For local/hybrid, keep them and set `mailbox=True`.

---

## Slash Commands

- `/new-agent <role>` — Scaffolds a new StandIn agent file with Agentverse registration comment, Chat Protocol, MongoDB collections, Gemini function calling, and correct uagents patterns.

---

## Registered Agent Addresses

*(Fill in after deploying each agent to Agentverse)*

| Agent | Agentverse Address |
|---|---|
| Orchestrator | |
| Engineering | |
| Design | |
| Product | |
| GTM | |
| Verifier | |
| Escalation | |
