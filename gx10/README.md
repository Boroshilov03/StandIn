# standin-gx10

Local FastAPI service for the **StandIn** project. Runs on the **ASUS Ascent GX10**
edge device. Performs privacy redaction and contradiction pre-check locally
before any workplace context reaches a cloud LLM (Gemini).

## What it does

1. **`POST /api/gx10/redact`** — strips secrets, customer names, PII, and
   confidential business language from documents before they leave the GX10.
2. **`POST /api/gx10/contradiction-check`** — detects contradictions between
   delegate-agent claims (e.g. Engineering says "blocked", GTM says "ready").
3. **`GET /api/gx10/trust-report/{workflow_id}`** — combined trust-layer report
   for the dashboard.
4. **`GET /health`** — liveness probe.

Each endpoint has a deterministic regex/rule pass first, then optionally calls
local Ollama (`gemma3:4b`) for semantic refinement. If Ollama times out or
returns invalid JSON, the deterministic output is used. The service never
crashes a request during the demo.

## Quickstart

```bash
cd standin-gx10
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Demo-safe (deterministic mock):
uvicorn app:app --host 0.0.0.0 --port 8001 --reload

# Live local inference (Ollama must be running):
GX10_MOCK=false uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

## Ollama setup on the GX10

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ollama serve   # default http://localhost:11434
```

## Environment

| Variable | Default | Notes |
|---|---|---|
| `GX10_MOCK` | `true` | If `true`, skip Ollama entirely. |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama daemon. |
| `OLLAMA_MODEL` | `gemma3:4b` | Pulled via `ollama pull`. |
| `OLLAMA_TIMEOUT_SECONDS` | `12` | Hard cap; falls back on timeout. |
| `PORT` | `8001` | FastAPI port. |

## Endpoint examples

### Health

```bash
curl -s http://localhost:8001/health
```

### Redact

```bash
curl -s -X POST http://localhost:8001/api/gx10/redact \
  -H "Content-Type: application/json" \
  -d '{
    "workflowId": "workflow_001",
    "documents": [
      {
        "id": "slack_eng_1",
        "owner": "Engineering",
        "type": "slack",
        "content": "Auth API is blocked. Customer ACME is affected. Token Bearer sk-prod-abc123xyz was exposed."
      },
      {
        "id": "jira_gtm_1",
        "owner": "GTM",
        "type": "jira",
        "content": "Press release is ready, but legal has not approved the confidential pricing language."
      }
    ]
  }'
```

### Contradiction check

```bash
curl -s -X POST http://localhost:8001/api/gx10/contradiction-check \
  -H "Content-Type: application/json" \
  -d '{
    "workflowId": "workflow_001",
    "claims": [
      {"owner":"Engineering","role":"Engineering Delegate","claim":"The API is blocked until Friday.","confidence":"high","sourceIds":["jira_api_241"]},
      {"owner":"GTM","role":"GTM Delegate","claim":"Launch is ready today and sales has been briefed.","confidence":"medium","sourceIds":["slack_gtm_2"]},
      {"owner":"Design","role":"Design Delegate","claim":"Launch page is finalized and handed off.","confidence":"high","sourceIds":["jira_des_118"]}
    ]
  }'
```

### Trust report

```bash
curl -s http://localhost:8001/api/gx10/trust-report/workflow_001
```

## Demo behavior

During the final demo, the dashboard should show:

- Privacy Redaction: **Complete**
- Documents processed: **7–12**
- Sensitive fields redacted: **5**
- Raw documents sent to cloud: **0**
- Claims verified: **9**
- Contradictions detected: **1**
- Escalation required: **Yes**
- Ran on: **ASUS GX10**

## Reliability over flash

Mock fallback is required by design. If local inference is flaky, the API still
returns demo-ready JSON so the rest of the pipeline keeps running.
