"""
auth0_ai.py — Auth0 for AI Agents integration for StandIn.

Three primitives wired into the agent network:

  1. Token Vault — per-user OAuth tokens for 3rd-party APIs (Slack, Google, Atlassian).
                   status_agent uses this so the brief reflects what *the user*
                   can see, not what a shared service account can see.

  2. CIBA (Async Authz) — pushes "approve this action" prompts to the user's phone
                   before perform_action executes send_slack / send_email /
                   schedule_meeting. Replaces the dashboard-only approval gate.

  3. FGA (Fine-Grained Authz) — filters historical_agent's RAG corpus to only
                   documents the requesting user is authorized to read.

DESIGN: every function has a graceful no-op fallback when AUTH0_DOMAIN is unset,
so the project still runs locally without an Auth0 tenant. `is_configured()`
tells callers whether the live integration is active.

ENV VARS (set in project-root .env):
    AUTH0_DOMAIN              tenant host, e.g. "standin.us.auth0.com"
    AUTH0_CLIENT_ID           M2M app client id
    AUTH0_CLIENT_SECRET       M2M app client secret
    AUTH0_AUDIENCE            usually "https://<AUTH0_DOMAIN>/api/v2/"

    AUTH0_CIBA_CLIENT_ID      (optional) separate CIBA-enabled client; falls
                              back to AUTH0_CLIENT_ID if unset
    AUTH0_CIBA_CLIENT_SECRET  (optional) likewise
    AUTH0_CIBA_BINDING_MSG    default human-readable string shown in the push

    AUTH0_FGA_API_URL         e.g. "https://api.us1.fga.dev"
    AUTH0_FGA_STORE_ID        FGA store id
    AUTH0_FGA_MODEL_ID        (optional) authorization model id
    AUTH0_FGA_CLIENT_ID       FGA M2M client (separate credential pair)
    AUTH0_FGA_CLIENT_SECRET   FGA M2M secret

References:
    Token Vault:  https://auth0.com/ai/docs/call-others-apis-on-users-behalf
    CIBA:         https://auth0.com/ai/docs/async-user-confirmation
    FGA:          https://auth0.com/ai/docs/authorization-for-rag
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from typing import Optional

log = logging.getLogger("auth0_ai")

# ── Config ─────────────────────────────────────────────────────────────────────

_DOMAIN          = os.getenv("AUTH0_DOMAIN", "").strip().rstrip("/")
_CLIENT_ID       = os.getenv("AUTH0_CLIENT_ID", "").strip()
_CLIENT_SECRET   = os.getenv("AUTH0_CLIENT_SECRET", "").strip()
_AUDIENCE        = os.getenv("AUTH0_AUDIENCE", "").strip() or (
    f"https://{_DOMAIN}/api/v2/" if _DOMAIN else ""
)

_CIBA_CLIENT_ID     = os.getenv("AUTH0_CIBA_CLIENT_ID", "").strip() or _CLIENT_ID
_CIBA_CLIENT_SECRET = os.getenv("AUTH0_CIBA_CLIENT_SECRET", "").strip() or _CLIENT_SECRET
_CIBA_BINDING_MSG   = os.getenv("AUTH0_CIBA_BINDING_MSG", "Approve StandIn agent action")

_FGA_API_URL       = os.getenv("AUTH0_FGA_API_URL", "").strip().rstrip("/")
_FGA_STORE_ID      = os.getenv("AUTH0_FGA_STORE_ID", "").strip()
_FGA_MODEL_ID      = os.getenv("AUTH0_FGA_MODEL_ID", "").strip()
_FGA_CLIENT_ID     = os.getenv("AUTH0_FGA_CLIENT_ID", "").strip()
_FGA_CLIENT_SECRET = os.getenv("AUTH0_FGA_CLIENT_SECRET", "").strip()

_REQUEST_TIMEOUT = 8.0

# ── M2M token cache ────────────────────────────────────────────────────────────

_token_cache: dict[str, tuple[str, float]] = {}  # cache_key -> (access_token, expires_at)


def is_configured() -> bool:
    """True when Auth0 base credentials are present. Other features layered on top."""
    return bool(_DOMAIN and _CLIENT_ID and _CLIENT_SECRET)


def ciba_configured() -> bool:
    return is_configured() and bool(_CIBA_CLIENT_ID and _CIBA_CLIENT_SECRET)


def fga_configured() -> bool:
    return bool(_FGA_API_URL and _FGA_STORE_ID and _FGA_CLIENT_ID and _FGA_CLIENT_SECRET)


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _http(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    body: Optional[dict] = None,
    form: Optional[dict] = None,
) -> tuple[int, dict | str]:
    """Tiny urllib wrapper. Returns (status, parsed_json_or_text)."""
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)

    data: bytes | None = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            return exc.code, str(exc)
    except Exception as exc:
        return 0, str(exc)


def _m2m_token(
    cache_key: str,
    domain: str,
    client_id: str,
    client_secret: str,
    audience: str,
) -> Optional[str]:
    cached = _token_cache.get(cache_key)
    if cached and cached[1] > time.time() + 30:
        return cached[0]

    status, payload = _http(
        f"https://{domain}/oauth/token",
        method="POST",
        body={
            "client_id":     client_id,
            "client_secret": client_secret,
            "audience":      audience,
            "grant_type":    "client_credentials",
        },
    )
    if status != 200 or not isinstance(payload, dict):
        log.warning("Auth0 M2M token fetch failed | status=%s | payload=%s", status, payload)
        return None

    token = payload.get("access_token")
    expires = time.time() + float(payload.get("expires_in", 3600))
    if not token:
        return None
    _token_cache[cache_key] = (token, expires)
    return token


def _management_token() -> Optional[str]:
    if not is_configured():
        return None
    return _m2m_token("mgmt", _DOMAIN, _CLIENT_ID, _CLIENT_SECRET, _AUDIENCE)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Token Vault — federated 3rd-party access tokens per user
# ═══════════════════════════════════════════════════════════════════════════════

def get_federated_token(user_email: str, connection: str) -> Optional[str]:
    """
    Retrieve the user's federated 3rd-party access token from Auth0's Token Vault.

    `connection` is the Auth0 connection name, e.g.:
        "slack-oauth", "google-oauth2", "atlassian"

    Returns None if Auth0 isn't configured, the user isn't found, or hasn't
    connected that provider — caller should fall back to env-var token.
    """
    if not (is_configured() and user_email and connection):
        return None

    mgmt = _management_token()
    if not mgmt:
        return None

    qs = urllib.parse.urlencode({
        "q":             f'email:"{user_email}"',
        "search_engine": "v3",
        "fields":        "user_id,identities",
    })
    status, users = _http(
        f"https://{_DOMAIN}/api/v2/users?{qs}",
        headers={"Authorization": f"Bearer {mgmt}"},
    )
    if status != 200 or not isinstance(users, list) or not users:
        log.info("Token Vault: no Auth0 user for %s (status=%s)", user_email, status)
        return None

    user_id = users[0].get("user_id")
    if not user_id:
        return None

    status, payload = _http(
        f"https://{_DOMAIN}/api/v2/users/{urllib.parse.quote(user_id)}",
        headers={"Authorization": f"Bearer {mgmt}"},
    )
    if status != 200 or not isinstance(payload, dict):
        return None

    for ident in payload.get("identities", []):
        if ident.get("connection") == connection or ident.get("provider") == connection:
            tok = ident.get("access_token")
            if tok:
                log.info("Token Vault hit | user=%s | connection=%s", user_email, connection)
                return tok

    log.info("Token Vault miss | user=%s | connection=%s", user_email, connection)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CIBA — push-based async user authorization
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_user_id(user_email: str) -> Optional[str]:
    """Resolve email -> Auth0 user_id (e.g. 'google-oauth2|123...'). None if not found."""
    mgmt = _management_token()
    if not mgmt:
        return None
    qs = urllib.parse.urlencode({
        "q":             f'email:"{user_email}"',
        "search_engine": "v3",
        "fields":        "user_id,identities,last_login",
    })
    status, users = _http(
        f"https://{_DOMAIN}/api/v2/users?{qs}",
        headers={"Authorization": f"Bearer {mgmt}"},
    )
    if status != 200 or not isinstance(users, list) or not users:
        return None
    # Prefer the most recently logged-in user when multiple exist (e.g. social + db)
    users.sort(key=lambda u: u.get("last_login") or "", reverse=True)
    return users[0].get("user_id")


def ciba_initiate(
    user_email: str,
    binding_message: Optional[str] = None,
    scope: str = "openid",
) -> Optional[str]:
    """
    Initiate a CIBA (Client-Initiated Backchannel Authentication) flow.

    Returns auth_req_id which the caller polls via ciba_poll(). The user sees
    a push notification in the Auth0 Guardian app with `binding_message`.

    Returns None when CIBA isn't configured — caller should fall back to the
    existing manual approval REST endpoint.
    """
    if not ciba_configured():
        return None

    user_id = _resolve_user_id(user_email)
    if not user_id:
        log.warning("CIBA initiate: no Auth0 user for email=%s", user_email)
        return None

    msg = (binding_message or _CIBA_BINDING_MSG)[:64]  # spec caps at 64
    status, payload = _http(
        f"https://{_DOMAIN}/bc-authorize",
        method="POST",
        form={
            "client_id":         _CIBA_CLIENT_ID,
            "client_secret":     _CIBA_CLIENT_SECRET,
            "binding_message":   msg,
            "scope":             scope,
            "login_hint":        json.dumps({
                "format":  "iss_sub",
                "iss":     f"https://{_DOMAIN}/",
                "sub":     user_id,
            }),
        },
    )
    if status not in (200, 201) or not isinstance(payload, dict):
        log.warning("CIBA initiate failed | status=%s | payload=%s", status, payload)
        return None
    return payload.get("auth_req_id")


def ciba_poll(auth_req_id: str) -> tuple[str, Optional[str]]:
    """
    Poll CIBA token endpoint. Returns (state, access_token).
        state in {"approved", "pending", "denied", "expired", "error"}
    """
    if not ciba_configured() or not auth_req_id:
        return "error", None

    status, payload = _http(
        f"https://{_DOMAIN}/oauth/token",
        method="POST",
        form={
            "grant_type":     "urn:openid:params:grant-type:ciba",
            "auth_req_id":    auth_req_id,
            "client_id":      _CIBA_CLIENT_ID,
            "client_secret":  _CIBA_CLIENT_SECRET,
        },
    )
    if status == 200 and isinstance(payload, dict) and payload.get("access_token"):
        return "approved", payload["access_token"]

    err = payload.get("error") if isinstance(payload, dict) else None
    if err == "authorization_pending":
        return "pending", None
    if err == "slow_down":
        return "pending", None
    if err == "access_denied":
        return "denied", None
    if err == "expired_token":
        return "expired", None
    return "error", None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. FGA — fine-grained authz for RAG retrieval
# ═══════════════════════════════════════════════════════════════════════════════

def _fga_token() -> Optional[str]:
    if not fga_configured():
        return None
    audience = "https://api.us1.fga.dev/" if "us1" in _FGA_API_URL else f"{_FGA_API_URL}/"
    return _m2m_token(
        "fga", "fga.us.auth0.com", _FGA_CLIENT_ID, _FGA_CLIENT_SECRET, audience,
    )


def fga_filter_doc_ids(user_email: str, doc_ids: list[str]) -> list[str]:
    """
    Given a list of candidate doc IDs, return only those the user can `viewer`.

    Uses FGA's batch_check (single round-trip). On failure or no config,
    returns the original list (fail-open — appropriate for hackathon demo;
    production should fail-closed).

    Expected FGA model:
        type user
        type document
            relations
                define viewer: [user, role#member]
        type role
            relations
                define member: [user]
    """
    if not (fga_configured() and user_email and doc_ids):
        return doc_ids

    tok = _fga_token()
    if not tok:
        return doc_ids

    checks = [
        {
            "tuple_key": {
                "user":     f"user:{user_email}",
                "relation": "viewer",
                "object":   f"document:{doc_id}",
            },
            "correlation_id": doc_id,
        }
        for doc_id in doc_ids
    ]
    body: dict = {"checks": checks}
    if _FGA_MODEL_ID:
        body["authorization_model_id"] = _FGA_MODEL_ID

    status, payload = _http(
        f"{_FGA_API_URL}/stores/{_FGA_STORE_ID}/batch-check",
        method="POST",
        headers={"Authorization": f"Bearer {tok}"},
        body=body,
    )
    if status != 200 or not isinstance(payload, dict):
        log.warning("FGA batch_check failed | status=%s — passing all docs through", status)
        return doc_ids

    allowed: list[str] = []
    for r in payload.get("result", []):
        if r.get("allowed"):
            cid = r.get("correlation_id")
            if cid:
                allowed.append(cid)

    log.info(
        "FGA filter | user=%s | input=%d | allowed=%d",
        user_email, len(doc_ids), len(allowed),
    )
    return allowed


# ═══════════════════════════════════════════════════════════════════════════════
# Status helper for /health and the dashboard
# ═══════════════════════════════════════════════════════════════════════════════

def status_summary() -> dict:
    return {
        "configured":       is_configured(),
        "domain":           _DOMAIN if is_configured() else None,
        "token_vault":      is_configured(),
        "ciba":             ciba_configured(),
        "fga":              fga_configured(),
    }
