# StandIn
<img width="2014" height="1226" alt="image" src="https://github.com/user-attachments/assets/bd704177-dac8-4501-ba62-a0828e79378c" />

**Stop attending meetings for information. Send your StandIn.**

StandIn is a multi-agent workplace coordination system that turns low-value status meetings into verified async workflows. Instead of pulling people into a meeting just to ask for updates, StandIn sends role-specific agents to gather context, redact sensitive information locally, detect contradictions, and return a verified brief with owners, evidence, action items, and escalation recommendations.

StandIn is not another meeting summarizer. It is a coordination layer designed to answer:

**Did this meeting need to happen at all?**

---

## What it does

A user asks:

> “Are we GO for Monday’s launch? Give me blockers only.”

StandIn:

1. Interprets the request with the Orchestrator Agent.
2. Gathers role-specific context from seeded Slack/Jira/project data.
3. Sends raw context to the ASUS GX10 Trust Layer before cloud reasoning.
4. Redacts sensitive data locally using Gemma 3 via Ollama plus deterministic rules.
5. Generates structured role claims.
6. Checks contradictions locally on the GX10.
7. Produces a final brief with an Evidence Passport and escalation recommendation.

The output is not just a summary. It is a verified coordination artifact.

---

## Why it is different

Most meeting AI tools summarize meetings after people have already spent the time.

StandIn works before the meeting becomes necessary.

| Meeting AI tools | StandIn |
|---|---|
| Summarize after meetings | Prevent unnecessary status meetings |
| Work from one transcript | Coordinate across role-specific agents |
| Produce notes | Produce verified claims |
| Send raw context to cloud | Redact locally on GX10 first |
| Give summaries | Give Evidence Passports |

---

## Architecture

```text
User Request
   ↓
Orchestrator Agent
   ↓
Status Agent
   ↓
Raw role data
   ↓
ASUS GX10 Trust Layer
   ├── local redaction
   ├── Gemma 3 via Ollama
   ├── schema validation
   └── fallback-safe logic
   ↓
Redacted role context
   ↓
Role claims
   ↓
GX10 contradiction pre-check
   ↓
Verifier merge layer
   ├── rule-based checks
   ├── GX10 checks
   └── LLM-assisted validation
   ↓
Evidence Passport
   ↓
Final Brief + Action Items + Escalation Decision
````

---

## Core components

### Backend agents

* **Orchestrator Agent**: routes user requests and coordinates workflows.
* **Status Agent**: gathers context, calls the GX10, generates role claims, and detects contradictions.
* **Historical Agent**: retrieves prior brief history and memory.
* **Perform Action Agent**: creates simulated follow-ups or escalation tasks.
* **Watchdog Agent**: monitors incomplete or stalled workflows.

### ASUS GX10 Trust Layer

A standalone FastAPI service running on the ASUS GX10. It handles privacy and verification before cloud reasoning.

It runs:

* FastAPI
* Ollama
* Gemma 3:4B
* deterministic regex redaction
* schema validation
* local contradiction rules
* fallback-safe model orchestration

Endpoints:

```text
GET  /health
POST /api/gx10/redact
POST /api/gx10/contradiction-check
GET  /api/gx10/trust-report/{workflowId}
```

---

## Repository structure

```text
StandIn/
  backend/
    agents/
    data_engineering/
    gx10_client.py
    main.py
    models.py
    test_orchestrator.py

  frontend/
    app.jsx
    agent-flow.jsx
    orchestration.jsx
    styles.css

  gx10/
    app.py
    gx10_trust.py
    ollama_client.py
    mock_outputs.py
    models.py
    requirements.txt
    test_redact_live.sh
    README.md

  db/
  services/
  scripts/
```

---

## Running the GX10 Trust Layer

SSH into the GX10:

```bash
ssh asus@gx10-5493
```

Start Ollama:

```bash
nohup ollama serve > ~/ollama.log 2>&1 &
curl http://localhost:11434/api/tags
```

Pull Gemma if needed:

```bash
ollama pull gemma3:4b
```

Start the GX10 service:

```bash
cd ~/standin-gx10
source ~/.venv/bin/activate
GX10_MOCK=false nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8001 > server.log 2>&1 &
```

Check health:

```bash
curl -s http://localhost:8001/health
```

Expected:

```json
{"status":"ok","service":"standin-gx10","ranOn":"ASUS_GX10"}
```

Watch logs:

```bash
tail -f ~/standin-gx10/server.log
```

---

## Testing GX10 redaction

Run:

```bash
cd ~/standin-gx10
chmod +x test_redact_live.sh
./test_redact_live.sh
```

Expected redactions:

```text
sarah.chen@standin.ai → [EMAIL_REDACTED]
415-555-0142 → [PHONE_REDACTED]
Bearer sk-prod-... → [SECRET_REDACTED]
ACME / Globex / Hooli → [CUSTOMER_REDACTED]
CVE-2026-1188 → [CVE_REDACTED]
confidential pricing → [CONFIDENTIAL_REDACTED]
```

A successful local Gemma run logs:

```text
mode=gemma_refined
```

If Gemma fails or returns invalid JSON, the system falls back safely:

```text
mode=fallback_deterministic
```

---

## Running the backend

From the repo root:

```bash
python backend/main.py
```

To test the orchestrator:

```bash
python backend/test_orchestrator.py "Are we GO for Monday's launch?"
```

If GX10 integration is active, backend logs should show:

```text
GX10 redaction for Engineering | status=passed
GX10 contradiction-check | found=1 | escalation=True
```

---

## Environment variables

Create a `.env` file from `.env.example`.

For backend GX10 integration:

```env
GX10_BASE_URL=http://gx10-5493:8001
GX10_ENABLED=true
GX10_TIMEOUT_SECONDS=60
```

If running backend on the GX10:

```env
GX10_BASE_URL=http://localhost:8001
```

If using Tailscale:

```env
GX10_BASE_URL=http://100.95.112.3:8001
```

Other variables:

```env
GEMINI_API_KEY=
MONGODB_URI=
```

Do not commit real `.env` files.

---

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

If using the Python static server:

```bash
python serve.py
```

---

## Evidence Passport

StandIn’s final output includes an Evidence Passport:

```json
{
  "claim": "Launch is ready today.",
  "owner": "GTM",
  "confidence": "medium",
  "contradiction": "Engineering reports the API is blocked until Friday.",
  "recommendedAction": "Escalate Engineering and GTM for a 15-minute launch readiness decision.",
  "escalationRequired": true
}
```

---

## Demo scenario

Prompt:

```text
Are we GO for Monday's launch?
```

Seeded role context contains a realistic contradiction:

* Engineering reports that the API is blocked.
* Design reports that the launch page is finalized.
* GTM reports that launch communications are ready.

StandIn detects the conflict and recommends a targeted escalation instead of another broad meeting.

Example output:

```text
Status: At risk
Blocker: API integration blocked
Contradiction: GTM/Design ready, Engineering blocked
Escalation: Yes
Recommended action: 15-minute Engineering + GTM launch readiness call
```

---

## Safety and reliability

The GX10 trust layer uses a fallback-safe design:

```text
Gemma valid output
   → mode=gemma_refined

Gemma timeout / malformed JSON / schema failure
   → mode=fallback_deterministic

Unexpected deterministic failure
   → mode=mock_fallback
```

This prevents local LLM failures from crashing the workflow.

---

## What we built

* Multi-agent backend workflow
* Orchestrator, Status, Historical, Watchdog, and Perform Action agents
* ASUS GX10 local trust layer
* Local Gemma 3:4B inference through Ollama
* Deterministic redaction fallback
* Local contradiction checking
* Evidence Passport generation flow
* React frontend components
* Seeded launch-readiness demo data

---

## What’s next

* Full Agentverse deployment
* Real Slack, Jira, Google Calendar, Drive, and GitHub integrations
* Running ingestion directly on the ASUS GX10
* Fail-closed enterprise privacy mode
* Persistent Evidence Passport history in MongoDB
* GX10 Trust Layer dashboard panel
* ElevenLabs executive audio brief
* Approval-gated action execution
* Meeting replacement analytics showing time saved and escalations avoided

---

## Why it matters

StandIn is not trying to remove humans from work. It removes the part of work where humans are used as routers, search engines, and status relays.

The future of meetings should not be:

> “Everyone join so we can figure out who knows what.”

It should be:

> “The agents already checked. Here are the blockers. Here is the evidence. These two people need to decide.”

**Meetings should be for judgment. StandIn handles the status transfer.**

```
```
