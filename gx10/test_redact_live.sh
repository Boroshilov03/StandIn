#!/usr/bin/env bash
# Live-mode redaction smoke test. Run on the GX10 (or from any host that can reach it).
#
# Usage:
#   ./test_redact_live.sh                # hits localhost:8001
#   HOST=192.168.1.42 ./test_redact_live.sh
#
# Prereqs on the GX10:
#   - ollama serve running, gemma3:4b pulled
#   - standin-gx10 service started with GX10_MOCK=false:
#       GX10_MOCK=false uvicorn app:app --host 0.0.0.0 --port 8001
set -euo pipefail

HOST="${HOST:-localhost}"
PORT="${PORT:-8001}"
URL="http://${HOST}:${PORT}/api/gx10/redact"

echo "==> POST ${URL}"
echo "==> Sending a meeting transcript loaded with PII, secrets, and confidential language."
echo

curl -sS -X POST "${URL}" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON' | (command -v jq >/dev/null && jq . || cat)
{
  "workflowId": "meeting_launch_review_2026_04_25",
  "documents": [
    {
      "id": "transcript_segment_1",
      "owner": "Engineering",
      "type": "meeting_transcript",
      "content": "Sarah Chen (sarah.chen@standin.ai, 415-555-0142) led the call. She said the auth API is blocked because customer ACME hit a regression last Tuesday. The on-call engineer rotated his Bearer sk-prod-9f2a8c1ebd7641a3 in production at 2:14 AM. Globex is also affected. Postmortem doc references CVE-2026-1188."
    },
    {
      "id": "transcript_segment_2",
      "owner": "GTM",
      "type": "meeting_transcript",
      "content": "Marcus from sales (marcus.lee@standin.ai) confirmed the press release is ready but legal flagged the confidential pricing tier ($249/seat enterprise) as draft pricing that cannot ship publicly. Hooli's renewal hangs on this. Call legal at +1 (650) 555-0199 before EOD."
    },
    {
      "id": "transcript_segment_3",
      "owner": "Design",
      "type": "meeting_transcript",
      "content": "Launch landing page is finalized. No blockers from design. API token api-test-abcd1234efgh was committed to a draft PR by accident — already rotated. Next sync: priya.r@standin.ai will dial in."
    }
  ]
}
JSON

echo
echo "==> Done. Check server logs for the mode line:"
echo "    tail -n 20 ~/standin-gx10/server.log | grep -E 'redact\\[.*\\] mode='"
