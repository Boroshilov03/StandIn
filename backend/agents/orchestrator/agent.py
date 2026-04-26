"""
StandIn Orchestrator — Chat Protocol entrypoint.

Only the orchestrator should be Agentverse-facing. Downstream agents are
treated as local workers reached over direct uAgents addresses.
"""

import asyncio
import json
import logging
import os
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

load_dotenv()

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from models import (
    ActionRequest,
    ActionResponse,
    FullBriefRequest,
    FullBriefResponse,
    IntentClassification,
    RAGRequest,
    RAGResponse,
)

_SEED = os.getenv("AGENTVERSE_SEED")
_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_LOGGER = logging.getLogger("standin_orchestrator")
_LOG_GEMINI_CLASSIFIER_IO = os.getenv("ORCH_LOG_GEMINI_CLASSIFIER_IO", "1").lower() not in {"0", "false", "no"}

_GEMINI_CLIENT = None


def _get_gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None and _GEMINI_KEY:
        from google import genai
        _GEMINI_CLIENT = genai.Client(api_key=_GEMINI_KEY)
    return _GEMINI_CLIENT


def _preview_text(value: str | None, max_len: int = 700) -> str:
    if not value:
        return ""
    one_line = " ".join(value.split())
    if len(one_line) <= max_len:
        return one_line
    return f"{one_line[:max_len]}...(truncated,{len(one_line)} chars)"


def _normalize_submit_endpoint(raw_endpoint: str | None) -> str | None:
    if not raw_endpoint:
        return None
    endpoint = raw_endpoint.rstrip("/")
    return endpoint if endpoint.endswith("/submit") else f"{endpoint}/submit"


_ENDPOINT = _normalize_submit_endpoint(
    os.getenv("ORCHESTRATOR_ENDPOINT", f"http://127.0.0.1:{_PORT}")
)
_AGENTVERSE = None

orchestrator = Agent(
    name="standin_orchestrator",
    seed=_SEED,
    port=_PORT,
    agentverse=_AGENTVERSE,
    mailbox=True,
    publish_agent_details=True,
    network="testnet"
)

def _normalize_agent_address(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip().strip("'").strip('"')
    return cleaned or None


STATUS_AGENT_ADDRESS = _normalize_agent_address(os.getenv("STATUS_AGENT_ADDRESS"))
HISTORICAL_AGENT_ADDRESS = _normalize_agent_address(os.getenv("HISTORICAL_AGENT_ADDRESS"))
PERFORM_ACTION_ADDRESS = _normalize_agent_address(os.getenv("PERFORM_ACTION_ADDRESS"))

chat_proto = Protocol(spec=chat_protocol_spec)
pending_requests: dict[str, dict] = {}
status_sessions: dict[str, str] = {}
# Tracks in-flight fanout pairs: merge_id → {sender, history, status}
fanout_state: dict[str, dict] = {}
# Tracks when each request was sent for RTT logging
_request_sent_at: dict[str, float] = {}
# Tracks deterministic follow-up state per chat sender
# sender → { "action": str, "context": dict, "created_at": float }
pending_followups: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Demo persona registry — populated dynamically from the seeded `users`
# collection (or the 001_users migration as a fallback) so that the
# orchestrator never hardcodes a persona list. The orchestrator acts as one
# fixed identity (env: ORCHESTRATOR_DEMO_USER_ID, default "user_alice") so
# action requests like "schedule a meeting with Ben" can resolve a concrete
# organizer, attendees, and team context.
# ---------------------------------------------------------------------------

_MONGODB_URI = os.getenv("MONGODB_URI", "").strip()


def _persona_first_name(record: dict) -> str:
    explicit = (record.get("firstName") or "").strip()
    if explicit:
        return explicit
    name = (record.get("name") or "").strip()
    if name:
        return name.split()[0]
    return (record.get("_id") or record.get("id") or "").strip()


def _normalize_persona(record: dict) -> dict:
    pid = (record.get("_id") or record.get("id") or "").strip()
    return {
        "id": pid,
        "name": (record.get("name") or pid).strip(),
        "first_name": _persona_first_name(record),
        "email": (record.get("email") or "").strip(),
        "team": (record.get("team") or "").strip(),
        "role": (record.get("role") or "").strip(),
    }


def _load_personas_from_mongo() -> list[dict]:
    if not _MONGODB_URI:
        return []
    try:
        from pymongo import MongoClient  # type: ignore[import-not-found]

        client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=2000)
        cursor = client["standin"]["users"].find({"_id": {"$ne": "standin_bot"}})
        records = list(cursor)
        client.close()
        return records
    except Exception:
        return []


def _load_personas_from_migration() -> list[dict]:
    try:
        import importlib

        mod = importlib.import_module("db.migrations.001_users")
        return list(getattr(mod, "USERS", []))
    except Exception:
        return []


def _build_demo_personas() -> dict[str, dict]:
    raw = _load_personas_from_mongo() or _load_personas_from_migration()
    personas: dict[str, dict] = {}
    for record in raw:
        norm = _normalize_persona(record)
        if norm["id"] and norm["id"] != "standin_bot":
            personas[norm["id"]] = norm
    if not personas:
        # Last-resort fallback so the agent boots even with no DB and no
        # importable migration. The id matches 001_users.py.
        personas["user_alice"] = {
            "id": "user_alice",
            "name": "Alice Chen",
            "first_name": "Alice",
            "email": "alice@standin.ai",
            "team": "Product",
            "role": "Product lead",
        }
    return personas


DEMO_PERSONAS: dict[str, dict] = _build_demo_personas()
DEMO_PERSONA_ID = os.getenv("ORCHESTRATOR_DEMO_USER_ID", "user_alice").strip()
DEMO_PERSONA = DEMO_PERSONAS.get(DEMO_PERSONA_ID) or next(iter(DEMO_PERSONAS.values()))

TEAM_ALIASES = {
    "engineering": "Engineering",
    "product": "Product",
}

CHANNEL_ID_TO_NAME = {
    "C01STANDUP1": "#product-standup",
    "C01DECIDE02": "#decisions-launch",
    "C01UPDATES3": "#general-updates",
    "C0AVDKLBQF6": "#standin-updates",
}

ACTION_HINTS = {
    "send_email": ("email", "mail"),
    "send_slack": ("slack", "message in slack", "post in slack"),
    "draft_slack": ("draft slack", "slack draft"),
    "create_jira": ("jira", "ticket", "issue"),
    "update_jira_status": ("move ticket", "update jira", "transition jira", "change ticket status"),
    "schedule_meeting": ("schedule", "book meeting", "set up meeting", "invite"),
    "create_action_item": ("action item", "todo", "task"),
    "post_brief": ("post brief", "save brief", "publish brief"),
}

_CLASSIFIER_PROMPT = """
You classify user requests for a coordination orchestrator called StandIn.

## Sub-agents available
- status_agent   : live status, blockers, conflict detection across teams (uses Slack + Jira + RAG)
- historical_agent: past decisions, meeting notes, previous discussions (uses MongoDB vector/keyword search)
- perform_action : send Slack, email, create Jira tickets, schedule meetings, create action items

## Return strict JSON with this schema
{
  "intent": "status_query|conflict_check|action_request|history_query|briefing_request",
  "teams": ["Engineering" | "Product" | "Operations],
  "topic": "short topic or null",
  "time_window": "short time window phrase or null",
  "action_type": "send_email|send_slack|draft_slack|create_jira|update_jira_status|schedule_meeting|create_action_item|post_brief|null",
  "action_payload_json": "JSON string for action payload or null",
  "confidence": 0.0
}

## Intent rules
- status_query     = current state / readiness / blockers for a team or project
- conflict_check   = contradictions, disagreements, inconsistencies between teams
- briefing_request = broad cross-team summary / executive brief
- history_query    = past decisions, previous meetings, what happened before,
                     OR any lookup about a specific person, ticket, or entity
                     (e.g. "anything about Derek", "what is Alice working on", "tell me about NOVA-141",
                      "give me information about NOVA-142", "what is NOVA-139")
- action_request   = asks to send/create/update/schedule/post something
- Calendar read requests (upcoming/current meetings) → status_query
- Past calendar/meeting history → history_query
- Calendar create/update requests → action_request (schedule_meeting)
- time_window should only be set when clearly present.
- action_payload_json must be a compact JSON object string when action_request.
- For create_jira payload: {summary, description, issuetype, priority, labels, status, sprint_name}
  defaults: issuetype=Task, priority=Medium, labels=["standin","auto-created"], status="To Do", sprint_name="Sprint 1".
- For schedule_meeting payload: duration_minutes=30, time_zone="UTC", attendees=[].
- For send_slack payload: include channel, default "#standin-updates" when unspecified.
""".strip()


def _extract_text(msg: ChatMessage) -> str:
    chunks: list[str] = []
    for item in msg.content:
        if isinstance(item, TextContent):
            chunks.append(item.text)
    return " ".join(chunks).strip()


_AGENT_MENTION_RE = re.compile(r"@agent1[a-z0-9]+", re.IGNORECASE)


def _strip_agent_mentions(text: str) -> str:
    """Remove `@agent1...` mentions injected by ASI:One chat clients."""
    return _AGENT_MENTION_RE.sub("", text or "").strip()


def _resolve_attendees_in_text(text: str, exclude_id: str = "") -> list[dict]:
    """
    Resolve teammate personas referenced by name in the user's message.
    Matches first name OR full name as a word. Excludes the demo persona itself
    (the orchestrator never invites itself).
    """
    if not text:
        return []
    lowered = text.lower()
    out: list[dict] = []
    seen: set[str] = set()
    for pid, p in DEMO_PERSONAS.items():
        if pid == exclude_id or pid in seen:
            continue
        first = p["first_name"].lower()
        full = p["name"].lower()
        if re.search(rf"\b{re.escape(first)}\b", lowered) or re.search(rf"\b{re.escape(full)}\b", lowered):
            out.append(p)
            seen.add(pid)
    return out


def _extract_requested_names(text: str) -> list[str]:
    """
    Extract human names explicitly mentioned in schedule-style requests.
    This is a lightweight heuristic used for response phrasing fallback when
    persona-directory resolution does not find a match.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    # Common pattern: "with Derek", "with Derek and Priya", etc.
    match = re.search(
        r"\bwith\s+([A-Za-z][A-Za-z'.-]*(?:\s+[A-Za-z][A-Za-z'.-]*)?(?:\s*(?:,|and)\s*[A-Za-z][A-Za-z'.-]*(?:\s+[A-Za-z][A-Za-z'.-]*)?)*)",
        raw,
        flags=re.IGNORECASE,
    )
    if not match:
        return []
    names_blob = match.group(1)
    parts = re.split(r"\s*(?:,|and)\s*", names_blob)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        name = part.strip().strip(".!?")
        if not name:
            continue
        # Ignore trailing intent text if the regex over-captured.
        name = re.sub(r"\s+(?:i|we|to|for)\b.*$", "", name, flags=re.IGNORECASE).strip()
        if not name:
            continue
        name = " ".join(token.capitalize() for token in name.split())
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


_AFFIRMATIVE_TOKENS = (
    "yes", "y", "yeah", "yep", "yup", "sure", "please", "ok", "okay",
    "do it", "go ahead", "go for it", "create it", "make it", "absolutely", "confirm",
)
_NEGATIVE_TOKENS = (
    "no", "n", "nope", "nah", "skip", "cancel", "don't", "do not", "not now",
)


def _starts_with_token(text: str, tokens: tuple[str, ...]) -> bool:
    t = text.strip().lower().rstrip(".!?")
    if not t:
        return False
    for tok in tokens:
        if t == tok or t.startswith(tok + " ") or t.startswith(tok + ",") or t.startswith(tok + "."):
            return True
    return False


def _is_affirmative(text: str) -> bool:
    return _starts_with_token(text, _AFFIRMATIVE_TOKENS)


def _is_negative(text: str) -> bool:
    return _starts_with_token(text, _NEGATIVE_TOKENS)


def _enrich_schedule_payload(payload: dict, text: str) -> tuple[dict, str | None]:
    """
    Fill in organizer/attendees/topic on a schedule_meeting payload using the
    fixed demo persona context. Returns (payload, clarification_message).

    If the user said "my teammate"/"colleague" without naming anyone, returns a
    clarification asking them to specify, instead of executing blindly.
    """
    persona = DEMO_PERSONA
    resolved = _resolve_attendees_in_text(text, exclude_id=persona["id"])

    # If Gemini already filled attendees with strings/dicts, try to keep email-shaped values.
    incoming = payload.get("attendees") or []
    incoming_emails: list[str] = []
    if isinstance(incoming, list):
        for item in incoming:
            if isinstance(item, str) and "@" in item:
                incoming_emails.append(item.strip())
            elif isinstance(item, dict) and isinstance(item.get("email"), str) and "@" in item["email"]:
                incoming_emails.append(item["email"].strip())

    if not resolved and not incoming_emails:
        lowered = (text or "").lower()
        if any(t in lowered for t in ("my teammate", "my colleague", "with someone", "with the team", "teammate", "colleague")):
            others = [p for pid, p in DEMO_PERSONAS.items() if pid != persona["id"]]
            roster = ", ".join(f"{p['first_name']} ({p['team']})" for p in others)
            clarification = (
                f"Who specifically should I invite? I'm acting as {persona['name']} ({persona['team']}). "
                f"Available teammates: {roster}."
            )
            return payload, clarification

    attendee_emails: list[str] = []
    seen: set[str] = set()
    for email in [persona["email"], *(p["email"] for p in resolved), *incoming_emails]:
        if email and email not in seen:
            attendee_emails.append(email)
            seen.add(email)
    payload["attendees"] = attendee_emails
    payload["organizer"] = persona["email"]

    if not payload.get("title") or payload.get("title") == "StandIn follow-up":
        if resolved:
            names = " + ".join([persona["first_name"], *(p["first_name"] for p in resolved)])
            payload["title"] = f"{names} sync"
        else:
            payload["title"] = f"{persona['first_name']} StandIn follow-up"

    payload["duration_minutes"] = int(payload.get("duration_minutes") or 30)
    payload["time_zone"] = payload.get("time_zone") or "America/Los_Angeles"

    # Default schedule slot: next day at a rounded hour (9:00 local).
    if not payload.get("start_time"):
        tz_name = str(payload.get("time_zone") or "America/Los_Angeles")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")
            payload["time_zone"] = "UTC"
        start_dt = (datetime.now(tz) + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        end_dt = start_dt + timedelta(minutes=payload["duration_minutes"])
        payload["start_time"] = start_dt.isoformat()
        payload["end_time"] = end_dt.isoformat()

    if not payload.get("description"):
        payload["description"] = (
            f"Requested by {persona['name']} via StandIn. Original request: {text or '(no context)'}"
        )

    return payload, None


def _detect_teams(text: str) -> list[str]:
    lowered = text.lower()
    out: list[str] = []
    for alias, canonical in TEAM_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered) and canonical not in out:
            out.append(canonical)
    return out


def _is_calendar_read_request(text: str) -> bool:
    lowered = text.lower()
    has_calendar = any(t in lowered for t in ("meeting", "meetings", "calendar", "event", "events"))
    has_read = any(t in lowered for t in ("what", "show", "list", "read", "upcoming", "next", "have", "find"))
    has_write = any(t in lowered for t in ("schedule", "book", "create", "set up", "invite", "add"))
    return has_calendar and has_read and not has_write


def _is_calendar_past_query(text: str) -> bool:
    lowered = text.lower()
    return any(t in lowered for t in ("past", "previous", "last", "earlier", "history", "happened", "had")) and any(
        t in lowered for t in ("meeting", "meetings", "calendar", "event", "events")
    )


def _infer_action_type(text: str) -> str | None:
    lowered = text.lower()
    for action_type, hints in ACTION_HINTS.items():
        if any(h in lowered for h in hints):
            if action_type == "send_slack" and "draft" in lowered:
                continue
            return action_type
    return None


def _infer_action_payload(text: str, action_type: str | None) -> dict:
    payload: dict[str, object] = {"original_request": text}
    if action_type in {"send_slack", "draft_slack"}:
        channel_match = re.search(r"(#\w[\w-]*)", text)
        payload["channel"] = channel_match.group(1) if channel_match else "#standin-updates"
        payload["text"] = _extract_slack_message_text(text)
    elif action_type == "send_email":
        payload.update({"to": [], "subject": "StandIn request", "body": text})
    elif action_type == "create_jira":
        payload["summary"] = text[:120]
        payload["description"] = text
        payload["issuetype"] = "Task"
        payload["priority"] = "Medium"
        payload["labels"] = ["standin", "auto-created"]
        payload["status"] = "To Do"
        payload["sprint_name"] = "Sprint 1"
    elif action_type == "update_jira_status":
        ticket = re.search(r"\b([A-Z]{2,10}-\d+)\b", text)
        payload.update({"ticket_id": ticket.group(1) if ticket else "", "new_status": "In Progress", "comment": text})
    elif action_type == "schedule_meeting":
        payload.update({"title": "StandIn follow-up", "attendees": [], "description": text})
        payload["duration_minutes"] = 30
        payload["time_zone"] = "UTC"
    elif action_type == "read_calendar_events":
        payload["max_results"] = 10
        payload["query"] = ""
        payload["time_min"] = ""
        payload["time_max"] = ""
        payload["description"] = text
    elif action_type == "create_action_item":
        payload.update({"description": text, "owner": "unassigned", "urgency": "medium"})
    elif action_type == "post_brief":
        payload.update({"brief_id": str(uuid.uuid4()), "brief_data": {"summary": text}})
    return payload


def _extract_slack_message_text(text: str) -> str:
    """
    Extract intended Slack message body from a natural-language request.
    Prevents sending the raw command text into Slack.
    """
    raw = (text or "").strip()
    quoted = re.search(r"[\"“](.+?)[\"”]", raw)
    if quoted and quoted.group(1).strip():
        return quoted.group(1).strip()

    patterns = [
        r"send (?:a )?(?:message|update) (?:in|on|to) slack[:,]?\s*(.+)$",
        r"post (?:a )?(?:message|update) (?:in|on|to) slack[:,]?\s*(.+)$",
        r"send (?:to )?slack[:,]?\s*(.+)$",
        r"slack[:,]?\s*(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, raw, flags=re.IGNORECASE)
        if m and m.group(1).strip():
            candidate = m.group(1).strip()
            candidate = re.sub(r"^(updating that[,.\s]*)", "", candidate, flags=re.IGNORECASE).strip()
            return candidate or "Quick update: completed."

    tail = re.search(r"\bthat\b[:,]?\s*(.+)$", raw, flags=re.IGNORECASE)
    if tail and tail.group(1).strip():
        candidate = tail.group(1).strip()
        candidate = re.sub(r"^(updating that[,.\s]*)", "", candidate, flags=re.IGNORECASE).strip()
        return candidate or "Quick update: completed."
    return "Quick update: completed."


def _friendly_channel_name(channel: str) -> str:
    c = (channel or "").strip()
    if not c:
        return "#standin-updates"
    if c.startswith("#"):
        return c
    return CHANNEL_ID_TO_NAME.get(c, "#standin-updates")


def _fallback_classification(text: str) -> IntentClassification:
    teams = _detect_teams(text)
    action_type = None if _is_calendar_read_request(text) else _infer_action_type(text)
    lowered = text.lower()
    if _is_calendar_past_query(text):
        intent = "history_query"
    elif _is_calendar_read_request(text):
        intent = "status_query"
    elif action_type:
        intent = "action_request"
    elif any(t in lowered for t in ("history", "previous", "earlier", "before", "decided", "past")):
        intent = "history_query"
    elif any(t in lowered for t in ("conflict", "contradiction", "inconsistent", "disagree")):
        intent = "conflict_check"
    elif any(t in lowered for t in ("briefing", "brief", "summary", "recap", "overview")):
        intent = "briefing_request"
    else:
        intent = "status_query"

    return IntentClassification(
        intent=intent,
        teams=teams,
        topic=text[:140],
        time_window=None,
        action_type=action_type,
        action_payload_json=json.dumps(_infer_action_payload(text, action_type)) if action_type else None,
        confidence=0.45,
    )


async def _classify(text: str) -> IntentClassification:
    if not _GEMINI_KEY:
        _LOGGER.info("Classification fallback engaged: GEMINI_API_KEY missing.")
        return _fallback_classification(text)

    try:
        from google.genai import types as gt

        client = _get_gemini_client()
        if _LOG_GEMINI_CLASSIFIER_IO:
            _LOGGER.info(
                "Gemini classifier request | "
                f"model={_GEMINI_MODEL} | "
                f"system_instruction='{_preview_text(_CLASSIFIER_PROMPT)}' | "
                f"contents='User request: {_preview_text(text)}'"
            )
        resp = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=f"User request:\n{text}",
            config=gt.GenerateContentConfig(
                system_instruction=_CLASSIFIER_PROMPT,
                response_mime_type="application/json",
                thinking_config=gt.ThinkingConfig(thinking_budget=0),
            ),
        )
        if _LOG_GEMINI_CLASSIFIER_IO:
            _LOGGER.info(f"Gemini classifier raw response | text='{_preview_text(resp.text)}'")
        payload = json.loads(resp.text)
        action_payload_json = payload.get("action_payload_json")
        if payload.get("intent") == "action_request" and not action_payload_json:
            action_payload_json = json.dumps(
                _infer_action_payload(text, payload.get("action_type"))
            )

        result = IntentClassification(
            intent=payload.get("intent", "status_query"),
            teams=payload.get("teams") or [],
            topic=payload.get("topic"),
            time_window=payload.get("time_window"),
            action_type=payload.get("action_type"),
            action_payload_json=action_payload_json,
            confidence=float(payload.get("confidence") or 0.0),
        )
        _LOGGER.info(
            f"Classification (Gemini) | intent={result.intent} | "
            f"teams={result.teams} | action_type={result.action_type} | "
            f"confidence={result.confidence:.2f}"
        )
        return result
    except Exception as exc:
        _LOGGER.warning(f"Gemini classification failed, using fallback: {exc}")
        return _fallback_classification(text)


def _enforce_calendar_routing(text: str, cls: IntentClassification) -> IntentClassification:
    if _is_calendar_past_query(text):
        cls.intent = "history_query"
        cls.action_type = None
        cls.action_payload_json = None
    elif _is_calendar_read_request(text):
        cls.intent = "status_query"
        cls.action_type = None
        cls.action_payload_json = None
    return cls


def _briefing_roles(classification: IntentClassification) -> list[str] | None:
    return classification.teams or None


def _persona_scoped_roles(user_text: str, classification: IntentClassification) -> list[str] | None:
    """
    Scope status queries by persona context.
    - If teams were explicitly extracted, keep them.
    - If the user asks about "my colleague(s)/teammate(s)/my team", resolve
      teammate names and use only those teams.
    """
    explicit = _briefing_roles(classification)
    if explicit:
        return explicit

    lowered = (user_text or "").lower()
    # Named teammate mention should scope roles even without "my colleague".
    matched_people = _resolve_attendees_in_text(user_text, exclude_id=DEMO_PERSONA["id"])
    if matched_people:
        teams = sorted({p.get("team", "") for p in matched_people if p.get("team")})
        return teams or None

    colleague_style = any(
        token in lowered
        for token in ("my colleague", "my colleagues", "my teammate", "my teammates", "my team")
    )
    if not colleague_style:
        return None

    # Otherwise, "my colleagues" means everyone except the persona itself.
    teammate_teams = sorted(
        {
            p.get("team", "")
            for pid, p in DEMO_PERSONAS.items()
            if pid != DEMO_PERSONA["id"] and p.get("team")
        }
    )
    return teammate_teams or None


def _format_status_response(msg: FullBriefResponse, intent: str) -> str:
    def _sentences(text: str, max_sentences: int = 2) -> str:
        t = (text or "").strip().replace("\n", " ")
        if not t:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", t)
        picked = [p.strip() for p in parts if p.strip()][:max_sentences]
        if not picked:
            return t
        return " ".join(picked)

    # Keep chat responses concise and decision-oriented.
    lines = [f"Confidence: {msg.overall_confidence:.2f} ({msg.mode})"]

    blocked = [r for r in msg.role_statuses if r.status == "blocked" or r.blockers]
    if blocked:
        lines.append("Blockers:")
        for r in blocked[:4]:
            blocker = r.blockers[0] if r.blockers else _sentences(r.summary, 1)
            lines.append(f"- {r.role}: {_sentences(blocker, 1)}")
    else:
        lines.append("No blockers reported across scoped roles.")

    lines.append("")
    lines.append("Quick status:")
    for r in msg.role_statuses[:4]:
        lines.append(f"- {r.role}: {_sentences(r.summary, 2)}")

    if intent == "conflict_check":
        if msg.contradictions:
            lines.append("")
            lines.append("Conflicts:")
            for entry in msg.contradictions[:3]:
                lines.append(f"- {_sentences(entry, 2)}")
        else:
            lines.append("")
            lines.append("Conflicts: none detected.")
    elif msg.recommended_action:
        lines.append("")
        lines.append(f"Suggested next step: {_sentences(msg.recommended_action, 2)}")

    return "\n".join(lines)


def _format_history_response(msg: RAGResponse) -> str:
    sources = ", ".join(msg.source_ids) if msg.source_ids else "none"
    return f"{msg.answer}\n\nSources: {sources}\nConfidence: {msg.confidence:.2f} via {msg.retrieval_method}"


def _format_action_response(msg: ActionResponse) -> str:
    if msg.success:
        out = msg.result or f"Action {msg.action_type} completed."
        if msg.stub:
            out += "\n\nNote: this was executed in stub mode."
        return out
    return msg.error or f"Action {msg.action_type} failed."


def _merge_fanout_reply(history: RAGResponse, status: FullBriefResponse) -> str:
    """Combine historical doc context with live status into one answer."""
    lines = []
    if history and history.answer and history.confidence > 0.3:
        lines.append("Historical context:")
        lines.append(history.answer)
        if history.source_ids:
            lines.append(f"Sources: {', '.join(history.source_ids[:4])} | confidence: {history.confidence:.2f} via {history.retrieval_method}")
        lines.append("")
    lines.append("Current live status:")
    lines.append(_format_status_response(status, "status_query"))
    return "\n".join(lines)


_FANOUT_TIMEOUT_SECS = int(os.getenv("FANOUT_TIMEOUT_SECS", "35"))


async def _fanout_timeout(ctx: Context, merge_id: str) -> None:
    await asyncio.sleep(_FANOUT_TIMEOUT_SECS)
    state = fanout_state.pop(merge_id, None)
    if state is None:
        return
    history_req_id = merge_id
    status_req_id = f"{merge_id}_s"
    pending_requests.pop(history_req_id, None)
    pending_requests.pop(status_req_id, None)
    _request_sent_at.pop(history_req_id, None)
    _request_sent_at.pop(status_req_id, None)
    history: RAGResponse | None = state["history"]
    status: FullBriefResponse | None = state["status"]
    ctx.logger.warning(
        f"FanOut timeout | merge={merge_id[:8]}… | "
        f"history={'ok' if history else 'missing'} | status={'ok' if status else 'missing'}"
    )
    if history and status:
        text = _merge_fanout_reply(history, status)
    elif history:
        text = _format_history_response(history)
    elif status:
        text = _format_status_response(status, "history_query")
    else:
        text = "Both downstream agents timed out. Please try again."
    await _send_chat_reply(ctx, state["sender"], text)


async def _send_chat_reply(ctx: Context, recipient: str, text: str) -> None:
    await ctx.send(
        recipient,
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid.uuid4(),
            content=[TextContent(type="text", text=text), EndSessionContent(type="end-session")],
        ),
    )


async def _dispatch_followup_create_jira(
    ctx: Context, sender: str, followup: dict
) -> None:
    """Execute a deferred create_jira action that was queued after a meeting was scheduled."""
    ctx_data = followup.get("context") or {}
    summary_seed = (ctx_data.get("summary") or ctx_data.get("description") or "Blocker tracked via StandIn").strip()
    description = (ctx_data.get("description") or summary_seed).strip()
    persona = DEMO_PERSONA

    payload = {
        "summary": summary_seed[:120],
        "description": (
            f"{description}\n\n"
            f"Requested by {persona['name']} ({persona['team']}). "
            f"Linked meeting: {ctx_data.get('calendar_html_link') or ctx_data.get('calendar_event_id') or 'n/a'}"
        ),
        "issuetype": "Task",
        "priority": "High",
        "labels": ["standin", "blocker", "auto-created"],
        "status": "To Do",
        "sprint_name": "Sprint 1",
    }

    request_id = str(uuid.uuid4())
    pending_requests[request_id] = {
        "sender": sender,
        "intent": "action_request",
        "action_type": "create_jira",
        "user_text": "(follow-up: create blocker ticket)",
    }
    import time as _time
    _request_sent_at[request_id] = _time.monotonic()
    ctx.logger.info(
        f"→ PerformAction (followup) | id={request_id} | action_type=create_jira | "
        f"summary='{payload['summary'][:60]}'"
    )
    await ctx.send(
        PERFORM_ACTION_ADDRESS,
        ActionRequest(
            request_id=request_id,
            action_type="create_jira",
            payload=json.dumps(payload),
            context=description,
            priority="normal",
            title=payload["summary"],
            summary=description,
            team=ctx_data.get("team") or "Engineering",
            owner=persona["id"],
            owner_name=persona["name"],
            risk="high",
        ),
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id))
    user_text_raw = _extract_text(msg)
    user_text = _strip_agent_mentions(user_text_raw)
    if not user_text:
        await _send_chat_reply(ctx, sender, "I did not receive any text to route.")
        return

    ctx.logger.info(
        f"Incoming | sender={sender[:24]}… | persona={DEMO_PERSONA['id']} | "
        f"text='{user_text[:200]}'"
    )

    # Deterministic follow-up handling: if we previously asked the user a yes/no
    # follow-up question (e.g. "create a Jira ticket?"), interpret their response
    # without sending it through the LLM classifier.
    followup = pending_followups.get(sender)
    if followup:
        if _is_affirmative(user_text):
            pending_followups.pop(sender, None)
            ctx.logger.info(
                f"Follow-up confirmed | sender={sender[:24]}… | action={followup.get('action')}"
            )
            if followup.get("action") == "create_jira":
                await _dispatch_followup_create_jira(ctx, sender, followup)
                return
        if _is_negative(user_text):
            pending_followups.pop(sender, None)
            ctx.logger.info(
                f"Follow-up declined | sender={sender[:24]}… | action={followup.get('action')}"
            )
            await _send_chat_reply(ctx, sender, "Understood — skipping the ticket.")
            return
        # Otherwise the user changed topic; clear stale follow-up and continue.
        pending_followups.pop(sender, None)

    request_id = str(uuid.uuid4())
    try:
        import time
        t_classify = time.monotonic()
        classification = _enforce_calendar_routing(user_text, await _classify(user_text))
        ctx.logger.info(
            f"Classified | intent={classification.intent} | teams={classification.teams} | "
            f"topic={classification.topic!r} | action_type={classification.action_type} | "
            f"confidence={classification.confidence:.2f} | classify_ms={int((time.monotonic()-t_classify)*1000)}"
        )

        pending_requests[request_id] = {
            "sender": sender,
            "intent": classification.intent,
        }

        ctx.logger.info(
            f"Routing | id={request_id} | intent={classification.intent} | "
            f"teams={classification.teams} | topic={classification.topic} | "
            f"action_type={classification.action_type} | confidence={classification.confidence:.2f}"
        )

        if classification.intent in {"status_query", "conflict_check", "briefing_request"}:
            session_id = status_sessions.get(sender)
            roles = _persona_scoped_roles(user_text, classification)
            ctx.logger.info(
                f"→ StatusAgent | id={request_id} | roles={roles} | "
                f"session_id={session_id} | dest={STATUS_AGENT_ADDRESS[:24]}… | "
                f"topic={classification.topic!r}"
            )
            _request_sent_at[request_id] = time.monotonic()
            await ctx.send(
                STATUS_AGENT_ADDRESS,
                FullBriefRequest(
                    request_id=request_id,
                    user_email=sender,
                    topic=classification.topic,
                    roles=roles,
                    context=user_text,
                    session_id=session_id,
                ),
            )
            return

        if classification.intent == "history_query":
            role_filter = classification.teams[0] if classification.teams else None
            history_req_id = request_id
            status_req_id  = f"{request_id}_s"

            fanout_state[request_id] = {
                "sender":  sender,
                "history": None,
                "status":  None,
            }
            pending_requests[history_req_id] = {
                "sender":   sender,
                "intent":   "fanout_history",
                "merge_id": request_id,
            }
            pending_requests[status_req_id] = {
                "sender":   sender,
                "intent":   "fanout_status",
                "merge_id": request_id,
            }

            ctx.logger.info(
                f"→ FanOut | id={request_id} | "
                f"HistoricalAgent+StatusAgent parallel | role_filter={role_filter} | "
                f"teams={classification.teams} | topic={classification.topic!r}"
            )
            asyncio.ensure_future(_fanout_timeout(ctx, request_id))
            _request_sent_at[history_req_id] = time.monotonic()
            _request_sent_at[status_req_id]  = time.monotonic()
            await asyncio.gather(
                ctx.send(HISTORICAL_AGENT_ADDRESS, RAGRequest(
                    request_id=history_req_id,
                    question=user_text,
                    role_filter=role_filter,
                    top_k=6,
                )),
                ctx.send(STATUS_AGENT_ADDRESS, FullBriefRequest(
                    request_id=status_req_id,
                    user_email=sender,
                    topic=classification.topic,
                    roles=classification.teams or None,
                    context=user_text,
                    session_id=status_sessions.get(sender),
                )),
            )
            return

        if classification.intent == "action_request":
            action_type = classification.action_type or _infer_action_type(user_text)
            if not action_type:
                pending_requests.pop(request_id, None)
                ctx.logger.warning(f"action_request but no action_type detected | id={request_id}")
                await _send_chat_reply(
                    ctx,
                    sender,
                    "I could not determine which action to run. Try asking explicitly to send Slack, send email, create Jira, schedule a meeting, or create an action item.",
                )
                return

            try:
                base_payload = json.loads(
                    classification.action_payload_json
                    or json.dumps(_infer_action_payload(user_text, action_type))
                )
                if not isinstance(base_payload, dict):
                    base_payload = _infer_action_payload(user_text, action_type)
            except json.JSONDecodeError:
                base_payload = _infer_action_payload(user_text, action_type)

            schedule_meta: dict | None = None
            if action_type in {"send_slack", "draft_slack"}:
                extracted_text = _extract_slack_message_text(user_text)
                base_payload["text"] = extracted_text
                if not base_payload.get("channel"):
                    base_payload["channel"] = "#standin-updates"
            if action_type == "schedule_meeting":
                base_payload, clarification = _enrich_schedule_payload(base_payload, user_text)
                if clarification:
                    pending_requests.pop(request_id, None)
                    ctx.logger.info(
                        f"schedule_meeting clarification needed | id={request_id} | "
                        f"persona={DEMO_PERSONA['id']}"
                    )
                    await _send_chat_reply(ctx, sender, clarification)
                    return
                schedule_meta = {
                    "title": base_payload.get("title", ""),
                    "description": base_payload.get("description", ""),
                    "attendees": list(base_payload.get("attendees", [])),
                    "team": "Engineering",  # demo: blocker assumed to live with engineering
                    "start_time": base_payload.get("start_time", ""),
                    "time_zone": base_payload.get("time_zone", "America/Los_Angeles"),
                    "colleague_names": [
                        p.get("first_name", p.get("name", ""))
                        for p in _resolve_attendees_in_text(user_text, exclude_id=DEMO_PERSONA["id"])
                    ],
                    "requested_names": _extract_requested_names(user_text),
                }
                ctx.logger.info(
                    f"schedule_meeting enriched | persona={DEMO_PERSONA['id']} | "
                    f"organizer={base_payload.get('organizer')} | "
                    f"attendees={base_payload.get('attendees')} | "
                    f"title='{base_payload.get('title')}'"
                )

            payload_json = json.dumps(base_payload)
            pending_requests[request_id] = {
                "sender": sender,
                "intent": "action_request",
                "action_type": action_type,
                "user_text": user_text,
                "action_payload": dict(base_payload),
                "schedule_meta": schedule_meta,
            }
            ctx.logger.info(
                f"→ PerformAction | id={request_id} | action_type={action_type} | "
                f"dest={PERFORM_ACTION_ADDRESS[:24]}… | payload_keys={list(base_payload.keys())}"
            )
            _request_sent_at[request_id] = time.monotonic()
            await ctx.send(
                PERFORM_ACTION_ADDRESS,
                ActionRequest(
                    request_id=request_id,
                    action_type=action_type,
                    payload=payload_json,
                    context=user_text,
                    priority="normal",
                    title=base_payload.get("title") or base_payload.get("summary") or "",
                    summary=base_payload.get("description") or user_text,
                    team=(schedule_meta or {}).get("team") or "",
                    owner=DEMO_PERSONA["id"],
                    owner_name=DEMO_PERSONA["name"],
                ),
            )
            return

        pending_requests.pop(request_id, None)
        ctx.logger.warning(f"Unclassified request | id={request_id} | intent={classification.intent}")
        await _send_chat_reply(ctx, sender, "I could not classify that request.")

    except Exception as exc:
        pending_requests.pop(request_id, None)
        ctx.logger.exception(f"handle_chat error | id={request_id} | {exc}")
        await _send_chat_reply(ctx, sender, "An internal error occurred. Please try again.")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    _ = ctx, sender, msg


@orchestrator.on_message(FullBriefResponse)
async def handle_status_response(ctx: Context, sender: str, msg: FullBriefResponse):
    import time
    rtt = int((time.monotonic() - _request_sent_at.pop(msg.request_id, time.monotonic())) * 1000)
    ctx.logger.info(
        f"← FullBriefResponse | id={msg.request_id} | rtt={rtt}ms | mode={msg.mode} | "
        f"escalation={msg.escalation_required} | confidence={msg.overall_confidence:.2f} | "
        f"contradictions={len(msg.contradictions)} | passports={len(msg.evidence_passports)} | "
        f"deltas={len(msg.delta_claims or [])}"
    )
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        return

    if pending.get("intent") == "fanout_status":
        merge_id = pending["merge_id"]
        state = fanout_state.get(merge_id)
        if state:
            state["status"] = msg
            ctx.logger.info(f"← FanOut status half arrived | merge={merge_id[:8]}…")
            if state["history"] is not None:
                text = _merge_fanout_reply(state["history"], state["status"])
                ctx.logger.info(f"→ FanOut merged reply | merge={merge_id[:8]}… | len={len(text)}")
                await _send_chat_reply(ctx, state["sender"], text)
                fanout_state.pop(merge_id, None)
        return

    status_sessions[pending["sender"]] = msg.session_id or status_sessions.get(pending["sender"], "")
    await _send_chat_reply(ctx, pending["sender"], _format_status_response(msg, pending["intent"]))


@orchestrator.on_message(RAGResponse)
async def handle_history_response(ctx: Context, sender: str, msg: RAGResponse):
    import time
    rtt = int((time.monotonic() - _request_sent_at.pop(msg.request_id, time.monotonic())) * 1000)
    ctx.logger.info(
        f"← RAGResponse | id={msg.request_id} | rtt={rtt}ms | method={msg.retrieval_method} | "
        f"confidence={msg.confidence:.2f} | sources={msg.source_ids}"
    )
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        return

    if pending.get("intent") == "fanout_history":
        merge_id = pending["merge_id"]
        state = fanout_state.get(merge_id)
        if state:
            state["history"] = msg
            ctx.logger.info(f"← FanOut history half arrived | merge={merge_id[:8]}… | conf={msg.confidence:.2f}")
            if state["status"] is not None:
                text = _merge_fanout_reply(state["history"], state["status"])
                ctx.logger.info(f"→ FanOut merged reply | merge={merge_id[:8]}… | len={len(text)}")
                await _send_chat_reply(ctx, state["sender"], text)
                fanout_state.pop(merge_id, None)
        return

    ctx.logger.info(f"→ User | id={msg.request_id} | reply_len={len(msg.answer)} chars")
    await _send_chat_reply(ctx, pending["sender"], _format_history_response(msg))


@orchestrator.on_message(ActionResponse)
async def handle_action_response(ctx: Context, sender: str, msg: ActionResponse):
    import time
    rtt = int((time.monotonic() - _request_sent_at.pop(msg.request_id, time.monotonic())) * 1000)
    ctx.logger.info(
        f"← ActionResponse | id={msg.request_id} | rtt={rtt}ms | type={msg.action_type} | "
        f"success={msg.success} | stub={msg.stub} | action_id={msg.action_id}"
    )
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        return

    reply_text = _format_action_response(msg)

    if msg.action_type in {"send_slack", "draft_slack"} and msg.success:
        payload = pending.get("action_payload") or {}
        channel = _friendly_channel_name(str(payload.get("channel", "")))
        reply_text = f"Message has been sent in {channel}."

    # For schedule_meeting, reply only with scheduling confirmation.
    # Do not auto-prompt Jira creation.
    if msg.action_type == "schedule_meeting" and msg.success:
        meta = pending.get("schedule_meta") or {}
        # Pull calendar event identifiers from the success result if perform_action
        # surfaced them (currently included in the result string).
        event_id_marker = "eventId="
        calendar_event_id = ""
        if msg.result and event_id_marker in msg.result:
            calendar_event_id = msg.result.split(event_id_marker, 1)[1].split()[0].strip()

        colleague = (
            (meta.get("colleague_names") or ["your colleague"])[0]
            if isinstance(meta.get("colleague_names"), list)
            else "your colleague"
        )
        if colleague == "your colleague":
            requested = meta.get("requested_names")
            if isinstance(requested, list) and requested:
                colleague = str(requested[0])
        when_text = "tomorrow at 9:00 AM"
        calendar_link = ""
        try:
            start_raw = str(meta.get("start_time") or "")
            tz_name = str(meta.get("time_zone") or "America/Los_Angeles")
            start_dt = datetime.fromisoformat(start_raw)
            tz = ZoneInfo(tz_name)
            when_text = start_dt.astimezone(tz).strftime("%B %d at %I:%M %p")
        except Exception:
            pass
        if msg.result:
            url_match = re.search(r"https?://\S+", msg.result)
            if url_match:
                calendar_link = url_match.group(0).rstrip(").,")
        reply_text = (
            f"I've talked to {colleague}'s agent to find a common available time. "
            f"I've scheduled a meeting for you and {colleague} on {when_text}."
        )
        if calendar_link:
            reply_text += f"\nCalendar link: {calendar_link}"

    if msg.action_type == "create_jira" and msg.success:
        reply_text += (
            f"\n\nTicket created on behalf of {DEMO_PERSONA['name']} ({DEMO_PERSONA['team']})."
        )

    await _send_chat_reply(ctx, pending["sender"], reply_text)


orchestrator.include(chat_proto, publish_manifest=True)


@orchestrator.on_event("startup")
async def on_startup(ctx: Context):
    from_env = lambda key: "env" if os.getenv(key) else "seed-derived"
    ctx.logger.info(f"Orchestrator online | address={ctx.agent.address} | port={_PORT}")
    ctx.logger.info(
        f"Gemini: {'configured — model=' + _GEMINI_MODEL if _GEMINI_KEY else 'NOT configured — fallback classifier active'}"
    )
    ctx.logger.info(
        f"Sub-agent addresses:\n"
        f"  status_agent      [{from_env('STATUS_AGENT_ADDRESS')}] = {STATUS_AGENT_ADDRESS}\n"
        f"  historical_agent  [{from_env('HISTORICAL_AGENT_ADDRESS')}] = {HISTORICAL_AGENT_ADDRESS}\n"
        f"  perform_action    [{from_env('PERFORM_ACTION_ADDRESS')}] = {PERFORM_ACTION_ADDRESS}"
    )
    ctx.logger.info(
        "Routing table: status/conflict/briefing → status_agent | "
        "history → fanout(historical+status) | action → perform_action"
    )
    ctx.logger.info(
        f"Demo persona: {DEMO_PERSONA['name']} <{DEMO_PERSONA['email']}> | "
        f"team={DEMO_PERSONA['team']} | role={DEMO_PERSONA['role']} | "
        f"override via ORCHESTRATOR_DEMO_USER_ID (one of: {', '.join(DEMO_PERSONAS.keys())})"
    )


if __name__ == "__main__":
    if _ENDPOINT:
        print(f"Orchestrator endpoint: {_ENDPOINT}")
    if _AGENTVERSE:
        print(f"Agentverse URL: {_AGENTVERSE}")
    orchestrator.run()
