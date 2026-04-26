import asyncio
import glob
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, UTC

from dotenv import load_dotenv
from uagents import Agent, Context, Model

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

from data_engineering.company_data import CALENDAR, JIRA, SLACK, USERS
from models import (
    Claim,
    EvidencePassport,
    FullBriefRequest,
    FullBriefResponse,
    MeetingResponse,
    VerifyRequest,
    VerifyResponse,
)
try:
    from services.calendar_service import list_events as list_calendar_events
except Exception:
    list_calendar_events = None

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
_SEED = os.getenv("STATUS_AGENT_SEED", "status_agent_standin_seed_v1")
_PORT = int(os.getenv("STATUS_AGENT_PORT", "8007"))
_ENDPOINT = os.getenv("STATUS_AGENT_ENDPOINT", f"http://127.0.0.1:{_PORT}/submit")
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_SLACK_BOT_TOKEN  = os.getenv("SLACK_BOT_TOKEN",  "")
_SLACK_USER_TOKEN = os.getenv("SLACK_USER_TOKEN",  "")
_LOGGER = logging.getLogger("status_agent")


def _ensure_event_loop() -> None:
    """Python 3.14 no longer provides an implicit main-thread loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


_ensure_event_loop()

# Channel name → Slack channel ID; populated lazily by _slack_list_channels()
_slack_ch_cache: dict[str, str] = {}
_slack_ch_cache_ts: float = 0.0

agent = Agent(
    name="status_agent",
    seed=_SEED,
    port=_PORT,
    endpoint=[f"http://localhost:{_PORT}/submit"],
    network="testnet"
)

_STALE_HOURS = 48  # claims sourced from docs older than this are flagged stale
_RAG_DOCS: list[dict] = []   # seed doc corpus loaded at startup

# Gemini client — created once to reuse TCP/TLS connection across all calls
_GEMINI_CLIENT = None


def _get_gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None and _GEMINI_KEY:
        try:
            from google import genai
        except ImportError as exc:
            # Keep the pipeline alive in environments that only have
            # google-generativeai installed; role synthesis already has
            # deterministic fallbacks and contradiction rules still run.
            _LOGGER.warning(f"Gemini client unavailable (google.genai import failed): {exc}")
            return None
        _GEMINI_CLIENT = genai.Client(api_key=_GEMINI_KEY)
    return _GEMINI_CLIENT

_TEAM_USERS: dict[str, set[str]] = {
    team: {k for k, v in USERS.items() if v["team"] == team}
    for team in ("Engineering", "Design", "GTM", "Product")
}

ALL_ROLES = ["Engineering", "Design", "GTM", "Product"]


# ---------------------------------------------------------------------------
# Role configs — controls tool queries and Gemini framing per role
# ---------------------------------------------------------------------------
ROLE_CONFIGS: dict[str, dict] = {
    "Engineering": {
        "team": "Engineering",
        "slack_queries": ["checkout API v2 migration", "NOVA-142 blocked", "deployment"],
        "jira_query": "checkout API blocked deployment",
        "lens": (
            "Precise and technical. Surface API status, deployment blockers, "
            "ticket states. Risk-first: default to high if uncertain."
        ),
        "default_risk": "high",
    },
    "Design": {
        "team": "Design",
        "slack_queries": ["launch page", "design assets", "sign-off", "final"],
        "jira_query": "launch page design assets handoff",
        "lens": (
            "Visual and completion-focused. Surface asset delivery, "
            "sign-off status, and any open design blockers."
        ),
        "default_risk": "low",
    },
    "GTM": {
        "team": "GTM",
        "slack_queries": ["launch email", "pricing", "legal approval", "comms"],
        "jira_query": "GTM launch email pricing legal approval",
        "lens": (
            "Market-focused. Surface launch comms status, "
            "approval gates, and send-time readiness."
        ),
        "default_risk": "medium",
    },
    "Product": {
        "team": None,  # sees all teams
        "slack_queries": ["launch readiness", "go no-go", "blocker", "deadline"],
        "jira_query": "launch alpha critical blocker readiness",
        "lens": (
            "Outcome-focused. Synthesise the cross-functional picture: "
            "critical path, go/no-go criteria, stakeholder risks."
        ),
        "default_risk": "medium",
    },
}


# ---------------------------------------------------------------------------
# Hardcoded fallbacks  (seeded conflict — must stay intact for the demo)
# ---------------------------------------------------------------------------
_FALLBACKS: dict[str, dict] = {
    "Engineering": {
        "summary": (
            "Backend is ready except the launch page checkout integration. "
            "NOVA-142 is blocked: the checkout endpoint changed from /v1/checkout "
            "to /v2/checkout last night. QA smoke test is also blocked pending that fix."
        ),
        "blockers": [
            "Checkout API changed /v1/checkout → /v2/checkout last night. "
            "Launch page integration must be updated (NOVA-142).",
            "QA smoke test blocked until NOVA-142 resolves (NOVA-143).",
        ],
        "claims": [
            {
                "claim": "Checkout API endpoint changed from /v1/checkout to /v2/checkout last night.",
                "source_ids": ["doc_api_contract_change", "NOVA-142", "msg_eng_api_change"],
                "confidence": 0.97, "risk": "high",
                "source_timestamp": JIRA["NOVA-142"].get("created"),
            },
            {
                "claim": "NOVA-142 is blocked — launch page integration not updated for v2 API.",
                "source_ids": ["NOVA-142", "doc_backend_ticket"],
                "confidence": 0.97, "risk": "high",
                "source_timestamp": JIRA["NOVA-142"].get("updated"),
            },
            {
                "claim": "QA smoke test sign-off blocked pending NOVA-142 resolution.",
                "source_ids": ["NOVA-143", "doc_qa_bug_report"],
                "confidence": 0.95, "risk": "high",
                "source_timestamp": JIRA["NOVA-143"].get("created"),
            },
        ],
    },
    "Design": {
        "summary": (
            "The launch page is final and ready to ship. All assets approved "
            "and delivered to Engineering. Design has no outstanding work before Monday."
        ),
        "blockers": [],
        "claims": [
            {
                "claim": "Launch page is final and ready to ship. All assets approved.",
                "source_ids": ["doc_design_asset_note", "msg_design_launch_ready", "NOVA-140"],
                "confidence": 0.96, "risk": "low",
                "source_timestamp": next(
                    (v["timestamp"] for v in SLACK.values() if v["role"] == "Design"), None
                ),
            },
            {
                "claim": "Design sign-off complete. Figma handoff delivered to Engineering.",
                "source_ids": ["doc_design_asset_note", "NOVA-140"],
                "confidence": 0.96, "risk": "low",
                "source_timestamp": JIRA.get("NOVA-140", {}).get("updated"),
            },
        ],
    },
    "GTM": {
        "summary": (
            "Launch email is drafted and internally reviewed. Blocked on legal pricing "
            "sign-off. No external comms have gone out yet. Send target is Monday 9:30 AM PT."
        ),
        "blockers": [
            "Legal pricing approval not received — launch email cannot be sent (NOVA-141).",
        ],
        "claims": [
            {
                "claim": "Launch email draft complete, awaiting legal pricing sign-off.",
                "source_ids": ["doc_gtm_notes", "NOVA-141", "msg_gtm_email_preview"],
                "confidence": 0.92, "risk": "medium",
                "source_timestamp": next(
                    (v["timestamp"] for v in SLACK.values() if v["role"] == "GTM"), None
                ),
            },
            {
                "claim": "Launch email send blocked until legal confirms pricing.",
                "source_ids": ["NOVA-141", "doc_gtm_notes"],
                "confidence": 0.93, "risk": "medium",
                "source_timestamp": JIRA.get("NOVA-141", {}).get("updated"),
            },
            {
                "claim": "Target send time: Monday 9:30 AM PT, 30 min after go-live.",
                "source_ids": ["doc_gtm_notes"],
                "confidence": 0.88, "risk": "low",
                "source_timestamp": JIRA.get("NOVA-141", {}).get("created"),
            },
        ],
    },
    "Product": {
        "summary": (
            "Launch Alpha is NOT GO. Two critical Engineering blockers (NOVA-142, NOVA-143) "
            "and one GTM blocker (NOVA-141) unresolved 48 h before Monday. "
            "Design is complete. Go/no-go decision required by Sunday 6 PM PT."
        ),
        "blockers": [
            "Engineering: NOVA-142 blocked — v2 checkout API integration not updated.",
            "Engineering: NOVA-143 blocked — QA sign-off depends on NOVA-142.",
            "GTM: NOVA-141 in review — launch email pending legal pricing approval.",
        ],
        "claims": [
            {
                "claim": "Launch Alpha is NOT GO as of Friday. Two critical Engineering blockers.",
                "source_ids": ["doc_launch_readiness", "doc_go_no_go", "NOVA-142", "NOVA-143"],
                "confidence": 0.95, "risk": "high",
                "source_timestamp": "2026-04-25T09:00:00Z",
            },
            {
                "claim": "Design complete — launch page assets signed off and delivered.",
                "source_ids": ["doc_design_asset_note", "NOVA-140"],
                "confidence": 0.96, "risk": "low",
                "source_timestamp": JIRA.get("NOVA-140", {}).get("updated"),
            },
            {
                "claim": "Go/no-go decision required by Sunday 6 PM PT.",
                "source_ids": ["doc_go_no_go"],
                "confidence": 0.94, "risk": "medium",
                "source_timestamp": "2026-04-25T09:15:00Z",
            },
            {
                "claim": "Beta NPS is 47 — above the 40 target.",
                "source_ids": ["doc_beta_feedback"],
                "confidence": 0.91, "risk": "low",
                "source_timestamp": "2026-04-24T16:00:00Z",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# TOOL STUBS
# Label each with the MCP server it will call once connected.
# Replace the body and set "connected": True in TOOL_REGISTRY.
# ---------------------------------------------------------------------------

def _slack_list_channels() -> dict[str, str]:
    """Fetch public channel name→id via bot token. Cached 5 minutes."""
    import time
    import urllib.parse
    import urllib.request as _ureq
    global _slack_ch_cache, _slack_ch_cache_ts
    if _slack_ch_cache and (time.time() - _slack_ch_cache_ts) < 300:
        return _slack_ch_cache
    try:
        params = urllib.parse.urlencode(
            {"types": "public_channel", "limit": "200", "exclude_archived": "true"}
        )
        req = _ureq.Request(
            f"https://slack.com/api/conversations.list?{params}",
            headers={"Authorization": f"Bearer {_SLACK_BOT_TOKEN}"},
        )
        with _ureq.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        if data.get("ok"):
            _slack_ch_cache = {f"#{c['name']}": c["id"] for c in data.get("channels", [])}
            _slack_ch_cache_ts = time.time()
    except Exception as exc:
        _LOGGER.debug(f"conversations.list failed: {exc}")
    return _slack_ch_cache


def _slack_search_via_user_token(queries: list[str], limit: int) -> list[dict]:
    """search.messages API — requires user token with search:read scope."""
    import urllib.parse
    import urllib.request as _ureq
    combined = " ".join(queries[:3])
    params = urllib.parse.urlencode(
        {"query": combined, "count": str(min(limit * 3, 30)), "highlight": "false"}
    )
    req = _ureq.Request(
        f"https://slack.com/api/search.messages?{params}",
        headers={"Authorization": f"Bearer {_SLACK_USER_TOKEN}"},
    )
    with _ureq.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    if not data.get("ok"):
        raise RuntimeError(f"search.messages: {data.get('error')}")
    results = []
    seen: set[str] = set()
    for match in data.get("messages", {}).get("matches", []):
        key = match.get("permalink") or match.get("ts", "")
        if key in seen:
            continue
        seen.add(key)
        ts = match.get("ts", "")
        try:
            iso_ts = datetime.fromtimestamp(float(ts), UTC).isoformat()
        except (ValueError, OSError):
            iso_ts = ts
        ch_name = f"#{match.get('channel', {}).get('name', '?')}"
        ch_id   = match.get("channel", {}).get("id", "")
        results.append({
            "content":     f"[{ch_name}] {match.get('username', '?')}: {match.get('text', '')[:400]}",
            "source_id":   f"slack_{ch_id}_{ts.replace('.', '_')}",
            "source_type": "slack",
            "timestamp":   iso_ts,
        })
    return results[:limit]


def _slack_history_search(queries: list[str], limit: int) -> list[dict]:
    """Fallback: conversations.history on up to 8 channels (bot token)."""
    import urllib.parse
    import urllib.request as _ureq
    ch_map = _slack_list_channels()
    if not ch_map:
        raise RuntimeError("No channels returned from conversations.list")
    q_lower = {q.lower() for q in queries}
    results: list[dict] = []
    seen_ts: set[str] = set()
    for n, (ch_name, ch_id) in enumerate(ch_map.items()):
        if n >= 8:
            break
        try:
            params = urllib.parse.urlencode({"channel": ch_id, "limit": "100"})
            req = _ureq.Request(
                f"https://slack.com/api/conversations.history?{params}",
                headers={"Authorization": f"Bearer {_SLACK_BOT_TOKEN}"},
            )
            with _ureq.urlopen(req, timeout=6) as r:
                ch_data = json.loads(r.read().decode())
        except Exception:
            continue
        if not ch_data.get("ok"):
            continue
        for msg in ch_data.get("messages", []):
            ts   = msg.get("ts", "")
            text = (msg.get("text") or "").strip()
            if not text or ts in seen_ts:
                continue
            if any(q in text.lower() for q in q_lower):
                seen_ts.add(ts)
                try:
                    iso_ts = datetime.fromtimestamp(float(ts), UTC).isoformat()
                except (ValueError, OSError):
                    iso_ts = ""
                results.append({
                    "content":     f"[{ch_name}] {msg.get('username', msg.get('user', '?'))}: {text[:400]}",
                    "source_id":   f"slack_{ch_id}_{ts.replace('.', '_')}",
                    "source_type": "slack",
                    "timestamp":   iso_ts,
                })
        if len(results) >= limit * 4:
            break
    return results[:limit]


def _tool_slack_search_local(queries: list[str], team: str | None, limit: int) -> list[dict]:
    """Seeded-data fallback — always available, no network needed."""
    results = []
    seen: set[str] = set()
    for q in queries:
        q_lower = q.lower()
        for msg in SLACK.values():
            if msg["id"] in seen:
                continue
            team_match = (team is None) or (msg.get("role", "").lower() == team.lower())
            text_match = (
                q_lower in msg["content"].lower()
                or q_lower in msg.get("channel", "").lower()
            )
            if team_match and text_match:
                seen.add(msg["id"])
                results.append({
                    "content":     f"[{msg['channel']}] {msg['sender_name']}: {msg['content']}",
                    "source_id":   msg["id"],
                    "source_type": "slack",
                    "timestamp":   msg["timestamp"],
                })
    return results[:limit]


async def _tool_slack_search(queries: list[str], team: str | None, limit: int) -> list[dict]:
    """
    Real Slack search with seeded-data fallback.
    Uses search.messages (SLACK_USER_TOKEN) or conversations.history (SLACK_BOT_TOKEN).
    Falls back to seeded SLACK dict when no token is configured or API fails.
    """
    if not (_SLACK_BOT_TOKEN or _SLACK_USER_TOKEN):
        return _tool_slack_search_local(queries, team, limit)
    try:
        if _SLACK_USER_TOKEN:
            results = await asyncio.to_thread(_slack_search_via_user_token, queries, limit)
        else:
            results = await asyncio.to_thread(_slack_history_search, queries, limit)
        return results if results else _tool_slack_search_local(queries, team, limit)
    except Exception as exc:
        _LOGGER.warning(f"Slack API search failed ({exc}) — using seeded data")
        return _tool_slack_search_local(queries, team, limit)


async def _tool_jira_search(query: str, team_users: set[str] | None, limit: int) -> list[dict]:
    """
    STUB — mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql
    Replace body: await searchJiraIssuesUsingJql(jql=f'project = NOVA AND text ~ "{query}"')
    """
    tokens = query.lower().split()
    if not tokens:
        return []
    q = query.lower()
    results = []
    for ticket in JIRA.values():
        text = (ticket["title"] + " " + ticket.get("description", "")).lower()
        assignee_match = (team_users is None) or (ticket.get("assignee") in team_users)
        if tokens[0] in text and assignee_match:
            results.append({
                "content": (
                    f"[{ticket['id']}] {ticket['title']} — "
                    f"{ticket['status'].upper()}, {ticket['priority']}. "
                    f"{ticket.get('description', '')[:160]}"
                ),
                "source_id": ticket["id"],
                "source_type": "jira",
                "timestamp": ticket.get("updated", ticket.get("created", "")),
            })
    return results[:limit]


async def _tool_rag_query(query: str, role_filter: str | None, limit: int) -> list[dict]:
    """
    Keyword search over the seed document corpus (12 JSON files).
    Runs locally — no message-passing latency.
    When MONGODB_URI + GEMINI_KEY are set, the historical_agent provides vector search
    via RAGRequest; this covers the keyword fallback path during Phase 1.
    """
    query_tokens = set(query.lower().split())
    scored: list[tuple[float, dict]] = []
    for doc in _RAG_DOCS:
        if role_filter and doc.get("role", "").lower() not in ("", role_filter.lower()):
            continue
        haystack = (
            doc.get("title", "") + " " +
            doc.get("content", "") + " " +
            " ".join(doc.get("tags", []))
        ).lower()
        title_tokens = set(doc.get("title", "").lower().split())
        body_hits  = sum(1 for t in query_tokens if t in haystack)
        title_hits = sum(2 for t in query_tokens if t in title_tokens)
        score = body_hits + title_hits
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "content":   doc.get("content", "")[:400],
            "source_id": doc.get("id", ""),
            "source_type": "seed_doc",
            "timestamp": doc.get("timestamp", ""),
        }
        for _, doc in scored[:limit]
    ]


async def _tool_google_drive_search(query: str, limit: int) -> list[dict]:
    """STUB — mcp__claude_ai_Google_Drive"""
    _LOGGER.debug(f"[STUB] Drive search not connected — query='{query}'")
    return []


async def _tool_notion_search(query: str, limit: int) -> list[dict]:
    """STUB — mcp__claude_ai_Notion__notion-search"""
    _LOGGER.debug(f"[STUB] Notion search not connected — query='{query}'")
    return []


async def _tool_web_search(query: str, limit: int) -> list[dict]:
    """STUB — WebSearch"""
    _LOGGER.debug(f"[STUB] Web search not connected — query='{query}'")
    return []


def _calendar_window_from_text(text: str | None) -> tuple[str, str]:
    """
    Build a future-looking ISO-8601 window from user text.
    Defaults to the next 7 days when no explicit range is present.
    """
    now = datetime.now(UTC)
    days = 7
    if text:
        lowered = text.lower()
        match = re.search(r"\bnext\s+(\d{1,2})\s+days?\b", lowered)
        if match:
            days = max(1, min(30, int(match.group(1))))
        elif "today" in lowered:
            days = 1
        elif "tomorrow" in lowered:
            days = 2
        elif "this week" in lowered:
            days = 7
    end = now + timedelta(days=days)
    return now.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


async def _tool_calendar_upcoming(context_text: str | None, limit: int) -> list[dict]:
    if list_calendar_events is None:
        return []
    try:
        time_min, time_max = _calendar_window_from_text(context_text)
        events = list_calendar_events(time_min=time_min, time_max=time_max, max_results=limit)
        return [
            {
                "content": (
                    f"{event.get('summary', '(untitled)')} | "
                    f"start={event.get('start', {}).get('dateTime') or event.get('start', {}).get('date', '')} | "
                    f"end={event.get('end', {}).get('dateTime') or event.get('end', {}).get('date', '')}"
                ),
                "source_id": event.get("id", ""),
                "source_type": "calendar",
                "timestamp": event.get("updated", ""),
            }
            for event in events
        ]
    except Exception:
        return []


TOOL_REGISTRY = {
    "slack":    {"fn": _tool_slack_search,        "connected": bool(_SLACK_BOT_TOKEN or _SLACK_USER_TOKEN), "mcp": "slack_api"},
    "jira":     {"fn": _tool_jira_search,         "connected": False, "mcp": "mcp__claude_ai_Atlassian"},
    "rag_docs": {"fn": _tool_rag_query,           "connected": True,  "mcp": "local_seed_corpus"},
    "drive":    {"fn": _tool_google_drive_search, "connected": False, "mcp": "mcp__claude_ai_Google_Drive"},
    "notion":   {"fn": _tool_notion_search,       "connected": False, "mcp": "mcp__claude_ai_Notion"},
    "web":      {"fn": _tool_web_search,          "connected": False, "mcp": "WebSearch"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_status(blockers: list[str], claims: list[Claim]) -> str:
    if blockers:
        return "blocked"
    if any(c.risk == "high" for c in claims):
        return "in_review"
    return "ready"


def _weighted_confidence(claims: list[Claim]) -> float:
    if not claims:
        return 0.5
    w = {"high": 1.0, "medium": 0.8, "low": 0.6}
    total = sum(c.confidence * w.get(c.risk, 0.8) for c in claims)
    norm  = sum(w.get(c.risk, 0.8) for c in claims)
    return round(total / norm, 2)


def _validate_synthesis(data: object) -> dict | None:
    if not isinstance(data, dict):
        return None
    if "summary" not in data or "claims" not in data:
        return None
    clean_claims = []
    for c in data.get("claims", []):
        if not isinstance(c, dict) or "claim" not in c:
            continue
        risk = c.get("risk", "medium")
        clean_claims.append({
            "claim":      str(c["claim"]),
            "source_ids": c["source_ids"] if isinstance(c.get("source_ids"), list) else [],
            "confidence": max(0.0, min(1.0, float(c.get("confidence", 0.8)))),
            "risk":       risk if risk in ("high", "medium", "low") else "medium",
        })
    return {
        "summary":  str(data["summary"]),
        "blockers": [str(b) for b in data.get("blockers", []) if b],
        "claims":   clean_claims,
    }


def _check_stale(responses: list[MeetingResponse]) -> list[str]:
    threshold = datetime.now(UTC) - timedelta(hours=_STALE_HOURS)
    stale = []
    for r in responses:
        for c in r.claims:
            if not c.source_timestamp:
                continue
            try:
                ts = datetime.fromisoformat(c.source_timestamp.replace("Z", "+00:00"))
                if ts < threshold:
                    stale.append(
                        f"[{r.role}] \"{c.claim[:55]}...\" "
                        f"(source: {c.source_timestamp})"
                    )
            except ValueError:
                pass
    return stale


# ---------------------------------------------------------------------------
# Session memory — brief history stored in MongoDB
# ---------------------------------------------------------------------------

_MONGODB_URI = os.getenv("MONGODB_URI", "")


def _get_db():
    if not _MONGODB_URI:
        raise RuntimeError("MONGODB_URI not set")
    from pymongo import MongoClient
    client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _load_last_brief(user_email: str) -> dict | None:
    """Load the most recent stored brief for this user. Returns raw dict or None."""
    if not _MONGODB_URI:
        return None
    try:
        db  = _get_db()
        doc = db["brief_history"].find_one(
            {"user_email": user_email},
            {"_id": 0},
            sort=[("saved_at", -1)],
        )
        return doc
    except Exception:
        return None


def _save_brief_async(brief_dict: dict) -> None:
    """Fire-and-forget — write brief to brief_history. Never raises."""
    if not _MONGODB_URI:
        return
    try:
        db = _get_db()
        db["brief_history"].insert_one(brief_dict)
    except Exception:
        pass


def _detect_deltas(
    current: list[MeetingResponse],
    previous_roles: dict,   # {role: {"status": str, "blockers": list, "confidence": float}}
) -> list[str]:
    """
    Compare current role responses against the previous brief snapshot.
    Returns human-readable change descriptions.
    """
    deltas: list[str] = []
    for r in current:
        prev = previous_roles.get(r.role)
        if not prev:
            deltas.append(f"[{r.role}] New role data — no prior brief to compare.")
            continue

        # Status change
        if prev.get("status") != r.status:
            deltas.append(
                f"[{r.role}] Status changed: {prev.get('status')} → {r.status}"
            )

        # New blockers
        prev_blockers = set(prev.get("blockers", []))
        curr_blockers = set(r.blockers)
        for b in curr_blockers - prev_blockers:
            deltas.append(f"[{r.role}] New blocker: \"{b[:80]}\"")
        for b in prev_blockers - curr_blockers:
            deltas.append(f"[{r.role}] Blocker resolved: \"{b[:80]}\"")

        # Significant confidence drop (> 0.1)
        conf_drop = prev.get("confidence", 1.0) - r.confidence
        if conf_drop > 0.10:
            deltas.append(
                f"[{r.role}] Confidence dropped "
                f"{prev.get('confidence', '?'):.2f} → {r.confidence:.2f}"
            )

        # New high-risk claims not in previous brief
        prev_claims = set(prev.get("claim_texts", []))
        for c in r.claims:
            if c.risk == "high" and c.claim not in prev_claims:
                deltas.append(
                    f"[{r.role}] New high-risk claim: \"{c.claim[:80]}\""
                )

    return deltas


# ---------------------------------------------------------------------------
# Phase 1 — per-role data gathering (parallel tool queries)
# ---------------------------------------------------------------------------

async def _gather_role_data(role: str, context_text: str | None = None) -> dict:
    cfg = ROLE_CONFIGS[role]
    team = cfg["team"]
    team_users = _TEAM_USERS.get(team) if team else None

    slack_task = asyncio.create_task(
        _tool_slack_search(cfg["slack_queries"], team, limit=6)
    )
    jira_task = asyncio.create_task(
        _tool_jira_search(cfg["jira_query"], team_users, limit=6)
    )
    rag_task = asyncio.create_task(
        _tool_rag_query(cfg["jira_query"], team, limit=4)
    )
    calendar_task = asyncio.create_task(_tool_calendar_upcoming(context_text, limit=8))

    slack_results, jira_results, rag_results, calendar_results = await asyncio.gather(
        slack_task, jira_task, rag_task, calendar_task
    )

    return {
        "role":           role,
        "lens":           cfg["lens"],
        "slack_messages": slack_results,
        "jira_tickets":   jira_results,
        "seed_docs":      rag_results,
        "calendar":       calendar_results or [
            v for v in CALENDAR.values()
            if team_users is None or any(u in v["attendees"] for u in team_users)
        ],
    }


# ---------------------------------------------------------------------------
# Phase 2 — per-role Gemini synthesis
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are StandIn, an AI coordination system that replaces low-value update meetings "
    "with verified async briefs. Synthesise information from multiple sources, preserve "
    "uncertainty, and never claim certainty without evidence. Separate facts, inferred "
    "risks, and recommended actions."
)

_SYNTHESIS_TMPL = """\
Role: {role}
Analyst lens: {lens}

The raw_data below was gathered in parallel from four sources simultaneously:
  • slack_messages — recent channel posts relevant to this role
  • jira_tickets   — open/blocked tickets assigned to this team
  • seed_docs      — internal docs (specs, decisions, API contracts, meeting notes)
  • calendar       — upcoming meetings involving this team

Cross-reference all four sources. A claim is stronger when multiple sources agree.
A blocker in Jira confirmed by a Slack message is high-confidence; a Jira ticket
with no Slack corroboration is medium-confidence.

Example — how to synthesise from parallel-gathered data:
  slack_messages: [{{"content": "[#engineering] Derek: checkout API changed /v1→/v2. Filed NOVA-142. Blocker for Monday.", "source_id": "msg_eng_api_change"}}]
  jira_tickets:   [{{"content": "[NOVA-142] Update launch page integration — BLOCKED critical. Checkout calls old /v1/checkout.", "source_id": "NOVA-142"}}]
  seed_docs:      [{{"content": "API contract updated 2026-04-25: /v2/checkout is now canonical. /v1 deprecated.", "source_id": "doc_api_contract"}}]
  → good output:
  {{
    "summary": "Engineering is blocked on NOVA-142. The checkout API migrated from /v1 to /v2 overnight; the launch page still calls the old endpoint and will fail at checkout on Monday unless updated.",
    "blockers": ["NOVA-142: launch page integration not updated for /v2/checkout endpoint"],
    "claims": [
      {{"claim": "Checkout endpoint changed from /v1/checkout to /v2/checkout last night.", "source_ids": ["msg_eng_api_change", "NOVA-142", "doc_api_contract"], "confidence": 0.97, "risk": "high"}},
      {{"claim": "Launch page integration is blocked — will fail at checkout on launch.", "source_ids": ["NOVA-142"], "confidence": 0.95, "risk": "high"}}
    ]
  }}

Now synthesise from the actual raw_data below.
Return ONLY valid JSON — no markdown, no extra keys:
{{
  "summary": "<one paragraph>",
  "blockers": ["<blocker string>", ...],
  "claims": [
    {{
      "claim": "<single factual statement>",
      "source_ids": ["<id>", ...],
      "confidence": <0.0-1.0>,
      "risk": "<high|medium|low>"
    }}
  ]
}}

Raw data:
{raw_data}
"""


async def _synthesize_role(role: str, raw: dict) -> dict | None:
    if not _GEMINI_KEY:
        return None
    try:
        from google.genai import types as gt

        client = _get_gemini_client()
        prompt = _SYNTHESIS_TMPL.format(
            role=role,
            lens=raw["lens"],
            raw_data=json.dumps(
                {k: v for k, v in raw.items() if k != "lens"},
                default=str,
            ),
        )
        resp = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=prompt,
            config=gt.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        return _validate_synthesis(json.loads(resp.text))
    except Exception as exc:
        _LOGGER.warning(f"Gemini synthesis failed for {role}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Phase 3 — contradiction detection
# ---------------------------------------------------------------------------

def _contradictions_rules(responses: list[MeetingResponse]) -> dict:
    """
    Rule engine — guaranteed to fire for the seeded scenario even without Gemini.
    Runs first; Gemini enriches the result when available.
    """
    status_map  = {r.role: r.status   for r in responses}
    blocker_map = {r.role: r.blockers for r in responses}

    contradictions: list[str] = []

    # Rule 1 — ready/blocked conflict between any two roles
    ready_roles   = [role for role, s in status_map.items() if s == "ready"]
    blocked_roles = [role for role, s in status_map.items() if s == "blocked"]
    for blocked in blocked_roles:
        for ready in ready_roles:
            first_blocker = blocker_map[blocked][0] if blocker_map[blocked] else "unknown blocker"
            contradictions.append(
                f"{ready} reports ready. {blocked} reports blocked. "
                f"Blocker: {first_blocker}"
            )

    # Rule 2 — high-risk claim with no source IDs
    unsupported = [
        f"[{r.role}] \"{c.claim[:60]}...\""
        for r in responses
        for c in r.claims
        if c.risk == "high" and not c.source_ids
    ]

    # Rule 3 — ticket blocked but a different role claims ready (belt + suspenders)
    eng_blocked = any(r.role == "Engineering" and r.status == "blocked" for r in responses)

    escalation_required = bool(contradictions) or eng_blocked

    if contradictions and any(
        "Engineering" in c and "Design" in c for c in contradictions
    ):
        reason = (
            "Design reports launch page ready. Engineering reports checkout "
            "integration blocked (NOVA-142). These claims directly conflict."
        )
        recommended = "Schedule 15-minute escalation with Design and Engineering only."
    elif escalation_required:
        reason = "High-priority Engineering blocker requires escalation before launch."
        recommended = "Resolve Engineering blockers before proceeding with go/no-go."
    else:
        reason = ""
        recommended = "No escalation required. All teams aligned."

    return {
        "contradictions":     contradictions,
        "unsupported_claims": unsupported,
        "escalation_required": escalation_required,
        "escalation_reason":   reason,
        "recommended_action":  recommended,
    }


_CONTRADICTION_TMPL = """\
Analyze these agent status reports and identify all contradictions, stale claims,
unsupported claims, and missing owners.

Reports:
{reports}

Return ONLY valid JSON — no markdown:
{{
  "contradictions":      ["..."],
  "stale_claims":        ["..."],
  "unsupported_claims":  ["..."],
  "missing_owners":      ["..."],
  "escalation_required": true,
  "escalation_reason":   "...",
  "recommended_action":  "..."
}}
"""


async def _detect_contradictions(responses: list[MeetingResponse]) -> dict:
    # Always run the rule engine first — it's the safety net
    rules = _contradictions_rules(responses)

    client = _get_gemini_client()
    if client is None or rules["contradictions"]:
        # Rules already found contradictions — authoritative, skip the ~20s Gemini call
        return {**rules, "stale_claims": [], "missing_owners": [], "unsupported_claims": rules.get("unsupported_claims", [])}

    try:
        from google.genai import types as gt

        reports_payload = [
            {
                "role":     r.role,
                "status":   r.status,
                "blockers": r.blockers,
                "claims": [
                    {
                        "claim":      c.claim,
                        "source_ids": c.source_ids,
                        "confidence": c.confidence,
                        "risk":       c.risk,
                    }
                    for c in r.claims
                ],
            }
            for r in responses
        ]
        resp = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=_CONTRADICTION_TMPL.format(
                reports=json.dumps(reports_payload, default=str)
            ),
            config=gt.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        gemini = json.loads(resp.text)

        # Merge: union rule findings + Gemini findings so neither source can drop detections.
        # Rules are authoritative on escalation_required — Gemini can only add, never remove.
        gemini_contradictions  = gemini.get("contradictions") or []
        gemini_unsupported     = gemini.get("unsupported_claims") or []
        merged_contradictions  = list(dict.fromkeys(rules["contradictions"] + gemini_contradictions))
        merged_unsupported     = list(dict.fromkeys(rules["unsupported_claims"] + gemini_unsupported))
        return {
            "contradictions":      merged_contradictions,
            "stale_claims":        gemini.get("stale_claims") or [],
            "unsupported_claims":  merged_unsupported,
            "missing_owners":      gemini.get("missing_owners") or [],
            "escalation_required": rules["escalation_required"] or bool(gemini.get("escalation_required")),
            "escalation_reason":   gemini.get("escalation_reason") or rules["escalation_reason"],
            "recommended_action":  gemini.get("recommended_action") or rules["recommended_action"],
        }
    except Exception as exc:
        _LOGGER.warning(f"Gemini contradiction detection failed: {exc}")
        return {**rules, "stale_claims": [], "missing_owners": []}


# ---------------------------------------------------------------------------
# Phase 4 — Evidence Passports
# ---------------------------------------------------------------------------

def _build_passports(
    responses: list[MeetingResponse],
    contradictions: list[str],
    escalation_required: bool,
    recommended_action: str,
) -> list[EvidencePassport]:
    passports: list[EvidencePassport] = []
    seen_claims: set[str] = set()

    for r in responses:
        for c in r.claims:
            # Include every high-risk claim and every claim involved in a contradiction
            in_contradiction = any(r.role in cd for cd in contradictions)
            if c.risk != "high" and not in_contradiction:
                continue
            key = f"{r.role}:{c.claim[:40]}"
            if key in seen_claims:
                continue
            seen_claims.add(key)

            conf_str = (
                "high"   if c.confidence >= 0.85 else
                "medium" if c.confidence >= 0.60 else
                "low"
            )
            passports.append(EvidencePassport(
                claim=c.claim,
                source=", ".join(c.source_ids[:3]) if c.source_ids else "no source",
                owner=c.owner,
                timestamp=c.source_timestamp or c.timestamp,
                confidence=conf_str,
                contradictions=[cd for cd in contradictions if r.role in cd],
                recommended_action=recommended_action,
                escalation_required=escalation_required,
            ))

    return passports


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@agent.on_event("startup")
async def on_startup(ctx: Context):
    global _RAG_DOCS
    seed_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data_engineering", "seed")
    )
    for path in glob.glob(os.path.join(seed_dir, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                _RAG_DOCS.append(json.load(f))
        except Exception as exc:
            ctx.logger.warning(f"Could not load seed doc {path}: {exc}")

    connected = [k for k, v in TOOL_REGISTRY.items() if v["connected"]]
    stub_count = len(TOOL_REGISTRY) - len(connected)
    ctx.logger.info(
        f"Status Agent online | address={ctx.agent.address} | port={_PORT}"
    )
    ctx.logger.info(
        f"Gemini: {'configured' if _GEMINI_KEY else 'not configured — seeded fallback'} | "
        f"Tools: {len(connected)} connected ({', '.join(connected)}), {stub_count} stubs | "
        f"RAG corpus: {len(_RAG_DOCS)} seed docs | "
        f"Roles: {ALL_ROLES}"
    )
    if not _MONGODB_URI:
        ctx.logger.warning(
            "MONGODB_URI not set — conversation memory, delta detection, "
            "and session history are DISABLED. All responses will use seeded fallback data."
        )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

@agent.on_message(FullBriefRequest)
async def handle_full_brief(ctx: Context, sender: str, msg: FullBriefRequest):
    # NOTE: this agent receives typed uAgents messages, NOT Chat Protocol.
    # Orchestrator must call: await ctx.send(STATUS_AGENT_ADDRESS, FullBriefRequest(...))
    ctx.logger.info(
        f"FullBriefRequest | id={msg.request_id} | "
        f"user={msg.user_email} | topic='{msg.topic}'"
    )
    try:
        brief = await _run_brief_pipeline(ctx, msg)
        await ctx.send(sender, brief)
    except Exception as exc:
        ctx.logger.error(f"Pipeline crashed unexpectedly: {exc}", exc_info=True)
        await ctx.send(sender, FullBriefResponse(
            request_id=msg.request_id,
            user_email=msg.user_email,
            role_statuses=[], contradictions=[], stale_claims=[],
            unsupported_claims=[], evidence_passports=[],
            escalation_required=False,
            escalation_reason="Internal error — pipeline crashed. Check agent logs.",
            recommended_action="Retry the request.",
            overall_confidence=0.0,
            mode="error",
            session_id=msg.session_id or str(uuid.uuid4()),
        ))


async def _run_brief_pipeline(ctx: Context, msg: FullBriefRequest) -> FullBriefResponse:
    import time
    t_start = time.monotonic()

    roles   = msg.roles or ALL_ROLES
    now     = datetime.now(UTC).isoformat()
    session_id = msg.session_id or str(uuid.uuid4())

    ctx.logger.info(
        f"Pipeline start | id={msg.request_id} | roles={roles} | "
        f"topic='{msg.topic}' | user={msg.user_email}"
    )

    # ── Load prior brief for delta detection (non-blocking) ──────────────
    last_brief = _load_last_brief(msg.user_email)
    previous_roles: dict = {}
    if last_brief:
        for rs in last_brief.get("role_statuses", []):
            previous_roles[rs["role"]] = {
                "status":      rs.get("status"),
                "blockers":    rs.get("blockers", []),
                "confidence":  rs.get("confidence", 1.0),
                "claim_texts": [c.get("claim", "") for c in rs.get("claims", [])],
            }
        ctx.logger.info(
            f"Session memory loaded | user={msg.user_email} | "
            f"prior_brief_at={last_brief.get('saved_at', '?')}"
        )

    # ── Phase 1: gather raw data per role (parallel) ──────────────────────
    t1 = time.monotonic()
    gather_tasks = {role: asyncio.create_task(_gather_role_data(role, msg.context)) for role in roles}
    gather_results = await asyncio.gather(*gather_tasks.values(), return_exceptions=True)
    t1_ms = int((time.monotonic() - t1) * 1000)
    raw_data: dict[str, dict] = {}
    tool_counts: dict[str, int] = {}
    for role, result in zip(roles, gather_results):
        if isinstance(result, Exception):
            ctx.logger.warning(f"Data gather failed for {role}: {result}")
            raw_data[role] = {
                "role": role, "lens": ROLE_CONFIGS[role]["lens"],
                "slack_messages": [], "jira_tickets": [], "seed_docs": [], "calendar": [],
            }
            tool_counts[role] = 0
        else:
            raw_data[role] = result
            tool_counts[role] = (
                len(result.get("slack_messages", [])) +
                len(result.get("jira_tickets", [])) +
                len(result.get("seed_docs", []))
            )

    ctx.logger.info(
        f"Phase 1 done | {t1_ms}ms | results_per_role={tool_counts}"
    )

    # ── Phase 2: Gemini synthesis — all roles in parallel ────────────────
    # All synthesis calls fire simultaneously; one slow Gemini response
    # does not delay the others.
    t2 = time.monotonic()
    synth_results = await asyncio.gather(
        *[_synthesize_role(role, raw_data[role]) for role in roles],
        return_exceptions=True,
    )
    t2_ms = int((time.monotonic() - t2) * 1000)
    ctx.logger.info(f"Phase 2 done | {t2_ms}ms (Gemini synthesis × {len(roles)} roles)")

    role_responses: list[MeetingResponse] = []
    used_fallback = False

    for role, synth in zip(roles, synth_results):
        if isinstance(synth, Exception):
            ctx.logger.warning(f"Synthesis task raised for {role}: {synth}")
            synth = None

        is_fallback = synth is None
        if is_fallback:
            synth = _FALLBACKS[role]
            used_fallback = True

        claims = [
            Claim(
                claim=c["claim"],
                source_ids=c.get("source_ids", []),
                owner=role,
                timestamp=now,
                source_timestamp=c.get("source_timestamp"),
                confidence=float(c.get("confidence", 0.9)),
                risk=c.get("risk", ROLE_CONFIGS[role]["default_risk"]),
            )
            for c in synth.get("claims", [])
        ]
        blockers = synth.get("blockers", [])

        role_responses.append(MeetingResponse(
            request_id=msg.request_id,
            user_email=msg.user_email,
            role=role,
            status=_derive_status(blockers, claims),
            summary=synth.get("summary", ""),
            blockers=blockers,
            claims=claims,
            confidence=_weighted_confidence(claims),
            mode="seeded" if is_fallback else "live",
        ))

    # ── Phase 3: contradiction detection ─────────────────────────────────
    t3 = time.monotonic()
    verdict = await _detect_contradictions(role_responses)
    stale   = _check_stale(role_responses)
    t3_ms   = int((time.monotonic() - t3) * 1000)
    ctx.logger.info(
        f"Phase 3 done | {t3_ms}ms | "
        f"contradictions={len(verdict['contradictions'])} | "
        f"escalation={verdict['escalation_required']} | "
        f"stale={len(stale)}"
    )

    # ── Phase 4: Evidence Passports ────────────────────────────────────────
    passports = _build_passports(
        role_responses,
        verdict["contradictions"],
        verdict["escalation_required"],
        verdict["recommended_action"],
    )

    # ── Overall confidence + delta detection ──────────────────────────────
    all_claims   = [c for r in role_responses for c in r.claims]
    overall_conf = _weighted_confidence(all_claims) if all_claims else 0.5
    mode         = "seeded" if used_fallback else "live"
    deltas       = _detect_deltas(role_responses, previous_roles) if previous_roles else []

    if deltas:
        ctx.logger.info(
            f"Deltas detected | {len(deltas)} change(s) since prior brief:\n"
            + "\n".join(f"  {d}" for d in deltas[:5])
            + (f"\n  … +{len(deltas)-5} more" if len(deltas) > 5 else "")
        )

    t_total_ms = int((time.monotonic() - t_start) * 1000)

    brief = FullBriefResponse(
        request_id=msg.request_id,
        user_email=msg.user_email,
        role_statuses=role_responses,
        contradictions=verdict["contradictions"],
        stale_claims=stale,
        unsupported_claims=verdict.get("unsupported_claims", []),
        evidence_passports=passports,
        escalation_required=verdict["escalation_required"],
        escalation_reason=verdict["escalation_reason"],
        recommended_action=verdict["recommended_action"],
        overall_confidence=overall_conf,
        mode=mode,
        session_id=session_id,
        delta_claims=deltas if deltas else None,
    )

    # ── Persist brief to history (fire-and-forget) ────────────────────────
    _save_brief_async({
        "request_id":    msg.request_id,
        "session_id":    session_id,
        "user_email":    msg.user_email,
        "topic":         msg.topic,
        "role_statuses": [
            {
                "role":        r.role,
                "status":      r.status,
                "blockers":    r.blockers,
                "confidence":  r.confidence,
                "claims":      [{"claim": c.claim, "risk": c.risk} for c in r.claims],
            }
            for r in role_responses
        ],
        "escalation_required": brief.escalation_required,
        "overall_confidence":  brief.overall_confidence,
        "saved_at":            now,
    })

    statuses = {r.role: r.status for r in role_responses}
    ctx.logger.info(
        f"Brief ready | {t_total_ms}ms total "
        f"(p1={t1_ms}ms gather, p2={t2_ms}ms synthesis, p3={t3_ms}ms contradict) | "
        f"roles={statuses} | contradictions={len(brief.contradictions)} | "
        f"passports={len(passports)} | escalation={brief.escalation_required} | "
        f"deltas={len(deltas)} | mode={mode}"
    )
    return brief


@agent.on_message(VerifyRequest)
async def handle_verify(ctx: Context, sender: str, msg: VerifyRequest):
    ctx.logger.info(
        f"VerifyRequest | id={msg.request_id} | "
        f"roles={[r.role for r in msg.responses]}"
    )
    try:
        verdict = await _detect_contradictions(msg.responses)
        stale   = _check_stale(msg.responses)

        passports = _build_passports(
            msg.responses,
            verdict["contradictions"],
            verdict["escalation_required"],
            verdict["recommended_action"],
        )

        response = VerifyResponse(
            request_id=msg.request_id,
            contradictions=verdict["contradictions"],
            stale_claims=stale,
            unsupported_claims=verdict.get("unsupported_claims", []),
            missing_owners=verdict.get("missing_owners", []),
            escalation_required=verdict["escalation_required"],
            escalation_reason=verdict["escalation_reason"],
            evidence_passports=passports,
            recommended_action=verdict["recommended_action"],
        )

        ctx.logger.info(
            f"VerifyResponse | contradictions={len(response.contradictions)} | "
            f"passports={len(passports)} | escalation={response.escalation_required}"
        )
        await ctx.send(sender, response)
    except Exception as exc:
        ctx.logger.error(f"VerifyRequest handler crashed: {exc}", exc_info=True)
        await ctx.send(sender, VerifyResponse(
            request_id=msg.request_id,
            contradictions=[], stale_claims=[], unsupported_claims=[],
            missing_owners=[], escalation_required=False,
            escalation_reason="Internal error — verifier crashed. Check agent logs.",
            evidence_passports=[],
            recommended_action="Retry the request.",
        ))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class _HealthResponse(Model):
    status: str
    agent: str
    gemini: str
    mongodb: str
    rag_docs: int
    timestamp: str


@agent.on_rest_get("/health", _HealthResponse)
async def health(ctx: Context) -> _HealthResponse:
    return _HealthResponse(
        status="ok",
        agent="status_agent",
        gemini="configured" if _GEMINI_KEY else "not configured",
        mongodb="configured" if _MONGODB_URI else "not configured",
        rag_docs=len(_RAG_DOCS),
        timestamp=datetime.now(UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# HTTP brief endpoint — lets the frontend request a brief without uAgents
# ---------------------------------------------------------------------------

class _BriefHttpRequest(Model):
    topic: str
    user_email: str = "demo@standin.ai"
    roles: list[str] = []


@agent.on_rest_post("/brief", _BriefHttpRequest, FullBriefResponse)
async def http_brief(ctx: Context, req: _BriefHttpRequest) -> FullBriefResponse:
    full_req = FullBriefRequest(
        request_id=str(uuid.uuid4()),
        user_email=req.user_email,
        topic=req.topic,
        roles=req.roles or ALL_ROLES,
        context="",
        session_id=req.user_email,
    )
    try:
        return await _run_brief_pipeline(ctx, full_req)
    except Exception as exc:
        ctx.logger.error(f"http_brief pipeline error: {exc}", exc_info=True)
        return FullBriefResponse(
            request_id=full_req.request_id,
            user_email=full_req.user_email,
            role_statuses=[], contradictions=[], stale_claims=[],
            unsupported_claims=[], evidence_passports=[],
            escalation_required=False,
            escalation_reason=f"Pipeline error: {exc}",
            recommended_action="Retry the request.",
            overall_confidence=0.0,
            mode="error",
            session_id=full_req.session_id,
        )


# ---------------------------------------------------------------------------
# HTTP briefs list — recent brief history for the dashboard
# ---------------------------------------------------------------------------

class _BriefSummary(Model):
    request_id: str
    user_email: str
    topic: str
    overall_confidence: float
    escalation_required: bool
    mode: str
    saved_at: str


class _BriefListResponse(Model):
    count: int
    briefs: list[_BriefSummary]


@agent.on_rest_get("/briefs", _BriefListResponse)
async def list_briefs(ctx: Context) -> _BriefListResponse:
    if not _MONGODB_URI:
        return _BriefListResponse(count=0, briefs=[])
    try:
        db   = _get_db()
        docs = list(
            db["brief_history"].find(
                {},
                {"_id": 0, "request_id": 1, "user_email": 1, "topic": 1,
                 "overall_confidence": 1, "escalation_required": 1, "mode": 1, "saved_at": 1},
            ).sort("saved_at", -1).limit(10)
        )
        briefs = [
            _BriefSummary(
                request_id=d.get("request_id", ""),
                user_email=d.get("user_email", ""),
                topic=d.get("topic", ""),
                overall_confidence=float(d.get("overall_confidence", 0.5)),
                escalation_required=bool(d.get("escalation_required", False)),
                mode=d.get("mode", ""),
                saved_at=d.get("saved_at", ""),
            )
            for d in docs
        ]
        return _BriefListResponse(count=len(briefs), briefs=briefs)
    except Exception as exc:
        ctx.logger.warning(f"list_briefs failed: {exc}")
        return _BriefListResponse(count=0, briefs=[])


if __name__ == "__main__":
    agent.run()

