# Auth0 for AI Agents — StandIn Setup

This guide wires StandIn to **Auth0 for AI Agents** — Auth0's product line built specifically for autonomous agent security, separate from generic Universal Login. It targets the LA Hacks 2026 *Best Use of Auth0 AI Agents* prize category.

## What's wired

| Auth0 AI primitive | StandIn surface | File |
|---|---|---|
| **Token Vault** — per-user OAuth tokens for 3rd-party APIs | `status_agent` Slack calls use the requesting user's Slack token instead of a shared bot token | [`backend/agents/status_agent/agent.py`](backend/agents/status_agent/agent.py) |
| **CIBA** — push approval to user's phone | `perform_action` initiates a CIBA push when a `send_slack` / `send_email` / `schedule_meeting` action hits the approval gate; `/approvals/ciba-poll` auto-executes on approve | [`backend/agents/perform_action/agent.py`](backend/agents/perform_action/agent.py) |
| **FGA** — fine-grained authz on RAG | `historical_agent` runs a batch_check against the FGA store and drops any document the requesting user is not authorized to read, before synthesis | [`backend/agents/historical_agent/agent.py`](backend/agents/historical_agent/agent.py) |

The shared client is [`backend/auth0_ai.py`](backend/auth0_ai.py). All three primitives are **no-op when env vars are missing** — the project still runs locally without Auth0 configured.

## .env additions

```bash
# Required — Management API M2M client
AUTH0_DOMAIN=standin.us.auth0.com
AUTH0_CLIENT_ID=...
AUTH0_CLIENT_SECRET=...
AUTH0_AUDIENCE=https://standin.us.auth0.com/api/v2/

# Optional — separate CIBA-enabled client (falls back to AUTH0_CLIENT_ID)
AUTH0_CIBA_CLIENT_ID=...
AUTH0_CIBA_CLIENT_SECRET=...
AUTH0_CIBA_BINDING_MSG=Approve StandIn agent action

# Optional — Auth0 FGA (for historical_agent RAG filtering)
AUTH0_FGA_API_URL=https://api.us1.fga.dev
AUTH0_FGA_STORE_ID=01H...
AUTH0_FGA_MODEL_ID=01H...
AUTH0_FGA_CLIENT_ID=...
AUTH0_FGA_CLIENT_SECRET=...
```

## Auth0 Dashboard — one-time setup

### 1. Create the tenant

1. Sign up at [auth0.com](https://auth0.com/ai) — pick the AI Agents trial.
2. Create a tenant (e.g. `standin`) in the **US** region.

### 2. Management API M2M app (Token Vault reads)

1. **Applications → Create Application** → "Machine to Machine".
2. Authorize for the **Auth0 Management API** with these scopes:
   - `read:users`
   - `read:user_idp_tokens`
3. Copy `Client ID` and `Client Secret` → `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET`.

### 3. Federated connections (Token Vault sources)

For each provider you want StandIn agents to act on behalf of:

- **Slack** — Authentication → Social → Slack. Use connection name `slack-oauth`. Enable "Sync user profile attributes at each login" + "Store IdP tokens". Required scopes: `chat:write`, `channels:read`, `search:read`.
- **Google** — Social → Google. Connection name `google-oauth2`. Scopes: `https://www.googleapis.com/auth/calendar`, `https://www.googleapis.com/auth/gmail.send`.
- **Atlassian** — Social → Custom OAuth2. Connection name `atlassian`. Scopes: `read:jira-work`, `write:jira-work`.

Users connect these by signing into StandIn through Auth0; the IdP tokens land in `identities[].access_token` on the user record, which `auth0_ai.get_federated_token()` retrieves.

### 4. CIBA configuration (phone approvals)

1. **Tenant Settings → Advanced** → enable "Client-Initiated Backchannel Authentication (CIBA)".
2. **Applications → Create Application** → "Regular Web Application" (or reuse the M2M app).
3. On that app: **Settings → Advanced → Grant Types** → enable **CIBA**.
4. **Authentication → MFA → Push Notifications** → install Guardian SDK, enable for the tenant.
5. Each demo user must enroll the **Auth0 Guardian** mobile app (App Store / Play Store) and link it to the Auth0 tenant.
6. Copy that app's `Client ID` / `Client Secret` → `AUTH0_CIBA_CLIENT_ID` / `AUTH0_CIBA_CLIENT_SECRET`.

### 5. FGA store (optional — for RAG filtering)

1. Go to [dashboard.fga.dev](https://dashboard.fga.dev) and create a store.
2. Paste this authorization model:

   ```dsl
   model
     schema 1.1

   type user

   type role
     relations
       define member: [user]

   type document
     relations
       define viewer: [user, role#member]
   ```

3. Add tuples per seed doc, e.g.:
   ```
   user:alice@centerfield.com  viewer  document:doc_seed_5
   role:engineering#member     viewer  document:doc_seed_3
   ```
4. **Settings → Authorized Clients → Create** an FGA M2M client. Copy `client_id` / `client_secret`.
5. Set `AUTH0_FGA_STORE_ID`, `AUTH0_FGA_MODEL_ID`, `AUTH0_FGA_CLIENT_ID`, `AUTH0_FGA_CLIENT_SECRET`.

## Verifying

1. Restart `python backend/main.py`.
2. Check the Auth0 chip in the StandIn HealthBar (top-right). When configured, the dot turns orange and `TV` / `CIBA` / `FGA` light up.
3. Hit the status endpoint directly:
   ```
   curl http://localhost:8008/auth0/status
   ```
4. Token Vault: trigger a brief — status_agent log should print `Auth0 Token Vault hit | user=… | slack token applied` and `slack_token=token_vault`.
5. CIBA: trigger an action that hits the approval gate (e.g. an escalation suggesting `send_slack`). Your phone receives the Guardian push. Then poll:
   ```
   curl -X POST http://localhost:8008/approvals/ciba-poll \
        -H 'Content-Type: application/json' \
        -d '{"action_id": "<id>"}'
   ```
   On `state: approved` the action auto-executes — no dashboard click required.
6. FGA: ask the historical agent something with `user_email` set; log shows `Auth0 FGA dropped N/M docs`.

## Demo narrative

> "StandIn agents act on behalf of real humans. Three Auth0 AI surfaces make that safe in production:
>
> 1. **Token Vault** — every user's brief uses *their* Slack identity. Service-account secrets aren't shared between agents and aren't visible in any agent's environment.
> 2. **CIBA** — before any outbound action, the user gets a push notification on their phone. No agent ever sends a Slack message or schedules a meeting without explicit human consent on a second device.
> 3. **FGA** — the historical agent only retrieves documents the user can read, enforced at query time — not after the fact in synthesis.
>
> No shared secrets. No agent over-privilege. No silent automation."
