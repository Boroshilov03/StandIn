"""
Quick Auth0 AI integration smoke test.
Run from project root:
    python backend/test_auth0.py [user@email.com]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import auth0_ai

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "mboroshilov@centerfield.com"

print("\n=== Auth0 AI Smoke Test ===\n")
s = auth0_ai.status_summary()
for k, v in s.items():
    mark = "OK" if v else "--"
    print(f"  {mark}  {k}: {v}")

print()

# ── Token Vault ───────────────────────────────────────────────────────────────
print("--- Token Vault ---")
tok = auth0_ai.get_federated_token(EMAIL, "slack-oauth")
if tok:
    print(f"  OK  Slack token retrieved for {EMAIL}: {tok[:20]}...")
else:
    print(f"  --  No Slack token for {EMAIL}.")
    print(f"     → User must sign in via Auth0 with Slack connected")
    print(f"     → Or create user in Auth0 dashboard + connect Slack social")

print()

# ── CIBA ─────────────────────────────────────────────────────────────────────
print("--- CIBA ---")
if not auth0_ai.ciba_configured():
    print("  --  CIBA not configured — set AUTH0_CIBA_CLIENT_ID in .env")
else:
    print(f"  Initiating CIBA push to {EMAIL}...")
    req_id = auth0_ai.ciba_initiate(EMAIL, "StandIn smoke test — approve me")
    if req_id:
        print(f"  OK  auth_req_id = {req_id}")
        print(f"  Polling once (expect 'pending' unless you approve on phone)...")
        state, _ = auth0_ai.ciba_poll(req_id)
        print(f"  State: {state}")
    else:
        print("  --  CIBA initiate returned None — check CIBA grant is enabled on the app")

print()

# ── FGA ───────────────────────────────────────────────────────────────────────
print("--- FGA ---")
if not auth0_ai.fga_configured():
    print("  --  FGA not configured — set AUTH0_FGA_* vars in .env")
else:
    test_ids = ["doc_seed_1", "doc_seed_2", "doc_seed_3"]
    allowed = auth0_ai.fga_filter_doc_ids(EMAIL, test_ids)
    print(f"  Input:   {test_ids}")
    print(f"  Allowed: {allowed}")

print()
print("Done.\n")
