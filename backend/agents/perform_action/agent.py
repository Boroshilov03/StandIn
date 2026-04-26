import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from uagents import Agent, Context, Model

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

from data_engineering.company_data import CALENDAR, JIRA, SLACK, USERS
from models import (
    ActionRequest,
    ActionResponse,
    ApproveRequest,
    ApproveResponse,
    FeedEntry,
    FeedResponse,
    GraphEdge,
    GraphNode,
    GraphResponse,
    PendingAction,
    PendingActionsResponse,
    RejectRequest,
    RejectResponse,
)
try:
    from schemas.action_payloads import normalize_action_payload
except Exception:
    def normalize_action_payload(action_type: str, payload: dict, context: dict):
        """Lightweight fallback normalizer. Returns: (ok, normalized_payload, error_message)"""
        if not isinstance(payload, dict):
            return False, {}, "Payload must be a JSON object."
        normalized = dict(payload)
        if action_type == "send_slack":
            owner = (context or {}).get("owner") or ""
            if owner and not normalized.get("user_id"):
                normalized["user_id"] = owner
        return True, normalized, None

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from services.calendar_service import create_event
    from services.calendar_service import add_reminder as add_calendar_reminder
    from services.calendar_service import get_event as get_calendar_event
    from services.calendar_service import list_events as list_calendar_events
    from services.slack_service import post_as_user
    from services.jira_service import create_ticket as create_jira_ticket
    from services.jira_service import update_ticket_status as update_jira_ticket_status
except Exception:
    create_event = None
    add_calendar_reminder = None
    get_calendar_event = None
    list_calendar_events = None
    post_as_user = None
    postAsBot = None
    create_jira_ticket = None
    update_jira_ticket_status = None

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
_SEED = os.getenv("PERFORM_ACTION_SEED", "perform_action_standin_seed_v1")
_PORT = int(os.getenv("PERFORM_ACTION_PORT", "8008"))
_MONGODB_URI = os.getenv("MONGODB_URI", "")
_LOGGER = logging.getLogger("perform_action")


def _ensure_event_loop() -> None:
    """Python 3.14 no longer provides an implicit main-thread loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


_ensure_event_loop()

agent = Agent(
    name="perform_action",
    seed=_SEED,
    port=_PORT,
    endpoint=[f"http://localhost:{_PORT}/submit"],
    network="testnet"
)


# ---------------------------------------------------------------------------
# MongoDB helper — shared by all actions that persist data
# ---------------------------------------------------------------------------

def _get_db():
    """Returns (db, action_log_collection) or raises if MongoDB not configured."""
    if not _MONGODB_URI:
        raise RuntimeError("MONGODB_URI not set")
    from pymongo import MongoClient
    client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=4000)
    db = client["standin"]
    return db


# Approval gating disabled: all actions execute immediately.
_APPROVAL_REQUIRED: set[str] = set()


def _save_pending_approval(
    action_id: str, action_type: str, payload: dict,
    priority: str, requested_by: str = "orchestrator",
    title: str = "", summary: str = "", team: str = "",
    owner: str = "", owner_name: str = "",
    ticket_status: str = "in_review", risk: str = "medium",
    stub: bool = True, escalation: dict | None = None,
) -> None:
    """Persist an action to pending_approvals collection."""
    if not _MONGODB_URI:
        return
    try:
        db = _get_db()
        db["pending_approvals"].insert_one({
            "action_id":      action_id,
            "action_type":    action_type,
            "payload":        payload,
            "priority":       priority,
            "requested_by":   requested_by,
            "status":         "pending",
            "created_at":     datetime.now(UTC).isoformat(),
            "title":          title or action_type.replace("_", " ").title(),
            "summary":        summary,
            "team":           team,
            "owner":          owner,
            "owner_name":     owner_name,
            "ticket_status":  ticket_status,
            "risk":           risk,
            "stub":           stub,
            "escalation":     escalation or {},
        })
    except Exception:
        pass


def _mark_approval_done(action_id: str, approved: bool, result: str) -> None:
    """Update a pending_approval record after decision."""
    if not _MONGODB_URI:
        return
    try:
        db = _get_db()
        db["pending_approvals"].update_one(
            {"action_id": action_id},
            {"$set": {
                "status":       "approved" if approved else "rejected",
                "result":       result,
                "resolved_at":  datetime.now(UTC).isoformat(),
            }},
        )
    except Exception:
        pass


def _log_action(action_id: str, action_type: str, payload: dict,
                 success: bool, result: str, stub: bool) -> None:
    """Fire-and-forget history entry — never raises."""
    if not _MONGODB_URI:
        return
    try:
        db = _get_db()
        db["action_log"].insert_one({
            "action_id":   action_id,
            "action_type": action_type,
            "payload":     payload,
            "success":     success,
            "result":      result,
            "stub":        stub,
            "created_at":  datetime.now(UTC).isoformat(),
        })
    except Exception:
        pass  # history logging must never crash the main flow


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def _action_send_email(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    STUB — mcp__claude_ai_Gmail (or mcp__claude_ai_Microsoft_365 for Outlook).
    Connect: call gmail authenticate → send message with to/subject/body from payload.

    payload: { to: list[str], subject: str, body: str, cc?: list[str] }
    """
    to      = payload.get("to", [])
    subject = payload.get("subject", "(no subject)")
    _LOGGER.info(
        f"[STUB] send_email | to={to} | subject='{subject}' | "
        f"priority={priority} — Gmail MCP not connected"
    )
    result = f"[stub] Email to {to} queued. Subject: '{subject}'"
    return True, result, True


async def _action_send_slack(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    Live Slack send via chat.postMessage (top-level only; no threads).

    payload: { text: str, channel?: str, user_id?: str }
    channel: optional slack_channels key (channelId, #name, or slackChannelId); defaults to #standin-updates.
    user_id: users._id (e.g. user_alice). Caller may merge ActionRequest.owner into payload before invoke.
    """
    text = (payload.get("text") or "").strip()
    if not text:
        return False, "send_slack requires non-empty payload.text", False

    user_id = (payload.get("user_id") or "").strip()
    if not user_id:
        return False, "send_slack requires user_id (users._id, e.g. user_alice).", False

    raw_ch = payload.get("channel")
    channel_key = None
    if isinstance(raw_ch, str):
        channel_key = raw_ch.strip() or None
    elif raw_ch is not None:
        channel_key = str(raw_ch).strip() or None

    if post_as_user is None:
        return False, "Slack service unavailable (missing dependencies or import path).", True
    if not _MONGODB_URI:
        return False, "send_slack requires MONGODB_URI for channel and user lookup.", True

    try:
        response = post_as_user(user_id, text, channel_key)
        ts = response.get("ts", "unknown")
        resolved = response.get("channel", channel_key or "default")
        result = f"Slack message posted as {user_id} to channel={resolved}. ts={ts}"
        return True, result, False
    except (ValueError, RuntimeError) as exc:
        return False, str(exc), False
    except Exception as exc:
        return False, f"Slack send failed: {exc}", False


async def _action_draft_slack(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    Post a draft/automated Slack message as the StandIn bot (no human approval gate).
    Used for watchdog alerts and escalation notices.

    payload: { text: str, channel?: str }
    """
    text = (payload.get("text") or "").strip()
    if not text:
        return False, "draft_slack requires non-empty payload.text", False

    raw_ch = payload.get("channel")
    channel_key = raw_ch.strip() if isinstance(raw_ch, str) else None

    if postAsBot is None:
        return False, "Slack service unavailable (import failed).", True
    if not _MONGODB_URI:
        return False, "draft_slack requires MONGODB_URI for channel lookup.", True

    try:
        response = postAsBot(text, channel_key)
        ts       = response.get("ts", "unknown")
        resolved = response.get("channel", channel_key or "default")
        result   = f"Draft Slack message (bot) posted to channel={resolved}. ts={ts}"
        return True, result, False
    except (ValueError, RuntimeError) as exc:
        return False, str(exc), False
    except Exception as exc:
        return False, f"draft_slack failed: {exc}", False


async def _action_create_jira(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    Live Jira create using services/jira_service.py
    payload: {
      summary?: str, description?: str, issuetype?: str, priority?: str,
      labels?: list[str], status?: str, assignee_account_id?: str, sprint_name?: str
    }
    """
    if create_jira_ticket is None:
        return False, "Jira service unavailable (missing dependencies or import path).", True

    summary = (payload.get("summary") or "").strip() or "StandIn follow-up ticket"
    description = (payload.get("description") or "").strip() or payload.get("original_request", "") or summary
    labels = payload.get("labels")
    if not isinstance(labels, list):
        labels = ["standin", "auto-created"]

    details = {
        "summary": summary,
        "description": description,
        "issuetype": (payload.get("issuetype") or "Task").strip() or "Task",
        "priority": (payload.get("priority") or "Medium").strip() or "Medium",
        "labels": labels,
        "status": (payload.get("status") or "To Do").strip() or "To Do",
        "assignee_account_id": (payload.get("assignee_account_id") or "").strip(),
        "sprint_name": (payload.get("sprint_name") or "Sprint 1").strip() or "Sprint 1",
    }

    try:
        _LOGGER.info(
            f"create_jira starting | action_id={action_id} | "
            f"summary='{details['summary'][:80]}' | issuetype={details['issuetype']} | "
            f"priority={details['priority']} | labels={details['labels']} | "
            f"sprint='{details['sprint_name']}'"
        )
        created = create_jira_ticket(details)
        payload["jira_issue_key"] = created.get("issueKey", "")
        payload["jira_url"] = created.get("url", "")
        warnings = []
        if created.get("transitionWarning"):
            warnings.append(f"transition: {created['transitionWarning']}")
        if created.get("sprintWarning"):
            warnings.append(f"sprint: {created['sprintWarning']}")
        suffix = f" | warnings: {'; '.join(warnings)}" if warnings else ""
        _LOGGER.info(
            f"create_jira done | action_id={action_id} | "
            f"issueKey={payload['jira_issue_key']} | url={payload['jira_url']} | "
            f"warnings={warnings or 'none'}"
        )
        result = f"Jira ticket created: {payload['jira_issue_key']} ({payload['jira_url']}){suffix}"
        return True, result, False
    except Exception as exc:
        _LOGGER.warning(f"create_jira failed | action_id={action_id} | error={exc}")
        return False, f"Jira create failed: {exc}", False


async def _action_update_jira_status(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    payload: { ticket_id: str, new_status: str, comment?: str }
    """
    if update_jira_ticket_status is None:
        return False, "Jira service unavailable (missing dependencies or import path).", True
    ticket_id = (payload.get("ticket_id") or payload.get("issue_key") or "").strip()
    new_status = (payload.get("new_status") or "In Progress").strip()
    if not ticket_id:
        return False, "update_jira_status requires payload.ticket_id", False
    try:
        update_jira_ticket_status(ticket_id, new_status)
        return True, f"Jira ticket {ticket_id} moved to '{new_status}'.", False
    except Exception as exc:
        return False, f"Jira status update failed: {exc}", False


async def _action_schedule_meeting(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    Live calendar event creation via services.calendar_service.create_event.

    payload: { title: str, attendees: list[str], start_time: str, duration_minutes: int, description?: str }
    """
    if create_event is None:
        result = "Calendar service unavailable (missing dependencies or import path)."
        return False, result, True
    try:
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        duration_minutes = int(payload.get("duration_minutes") or 30)
        if duration_minutes <= 0:
            duration_minutes = 30
        if not start_time:
            default_start = datetime.now(UTC) + timedelta(hours=1)
            start_time = default_start.isoformat()
        if start_time and not end_time and duration_minutes > 0:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_time = (start_dt + timedelta(minutes=duration_minutes)).isoformat()

        event_details = {
            "summary": payload.get("title", "StandIn follow-up"),
            "description": payload.get("description", ""),
            "start": start_time,
            "end": end_time,
            "timezone": payload.get("time_zone", "UTC"),
            "attendees": payload.get("attendees", []),
            "reminders": payload.get("reminders", []),
        }
        if not event_details["start"] or not event_details["end"]:
            return False, "schedule_meeting requires start_time and end_time (or duration_minutes).", False

        _LOGGER.info(
            f"schedule_meeting starting | action_id={action_id} | "
            f"title='{event_details['summary']}' | start={event_details['start']} | "
            f"end={event_details['end']} | tz={event_details['timezone']} | "
            f"attendees={event_details['attendees']}"
        )
        created = create_event(event_details)
        payload["calendar_event_id"] = created.get("id")
        payload["calendar_html_link"] = created.get("htmlLink")
        _LOGGER.info(
            f"schedule_meeting done | action_id={action_id} | "
            f"eventId={created.get('id')} | htmlLink={created.get('htmlLink')} | "
            f"status={created.get('status')}"
        )
        result = (
            f"Calendar event created. eventId={created.get('id')} "
            f"link={created.get('htmlLink', '')}"
        )
        return True, result, False
    except Exception as exc:
        _LOGGER.warning(f"schedule_meeting failed | action_id={action_id} | error={exc}")
        return False, f"Calendar scheduling failed: {exc}", False


async def _action_add_calendar_reminder(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    Adds or updates reminders on an existing Google Calendar event.

    payload: { event_id: str, reminders: list[dict] }
    """
    _ = action_id
    _ = priority
    if add_calendar_reminder is None:
        result = "Calendar service unavailable (missing dependencies or import path)."
        return False, result, True

    event_id = (payload.get("event_id") or "").strip()
    reminders = payload.get("reminders", [])
    if not event_id:
        return False, "add_calendar_reminder requires payload.event_id", False
    if not isinstance(reminders, list) or not reminders:
        return False, "add_calendar_reminder requires a non-empty payload.reminders list", False

    try:
        updated = add_calendar_reminder(event_id, reminders)
        payload["calendar_event_id"] = updated.get("id", event_id)
        payload["calendar_html_link"] = updated.get("htmlLink")
        result = f"Calendar reminders updated. eventId={event_id}"
        return True, result, False
    except Exception as exc:
        return False, f"Calendar reminder update failed: {exc}", False


def _compact_calendar_event(event: dict) -> dict:
    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", ""),
        "description": event.get("description", ""),
        "start": event.get("start", {}),
        "end": event.get("end", {}),
        "attendees": event.get("attendees", []),
        "htmlLink": event.get("htmlLink", ""),
        "status": event.get("status", ""),
    }


async def _action_read_calendar_events(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    Read Google Calendar events.

    payload:
    - list mode: { time_min?: str, time_max?: str, max_results?: int, query?: str }
    - single mode: { event_id: str }
    """
    _ = action_id
    _ = priority
    if list_calendar_events is None or get_calendar_event is None:
        result = "Calendar service unavailable (missing dependencies or import path)."
        return False, result, True

    try:
        event_id = (payload.get("event_id") or "").strip()
        if event_id:
            event = get_calendar_event(event_id)
            payload["event"] = _compact_calendar_event(event)
            result = json.dumps({"mode": "single", "event": payload["event"]})
            return True, result, False

        events = list_calendar_events(
            time_min=payload.get("time_min") or payload.get("timeMin"),
            time_max=payload.get("time_max") or payload.get("timeMax"),
            max_results=int(payload.get("max_results", 10)),
            query=payload.get("query"),
        )
        compact_events = [_compact_calendar_event(event) for event in events]
        payload["events"] = compact_events
        payload["event_count"] = len(compact_events)
        result = json.dumps({"mode": "list", "count": len(compact_events), "events": compact_events})
        return True, result, False
    except Exception as exc:
        return False, f"Calendar read failed: {exc}", False


async def _action_create_action_item(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    LIVE when MONGODB_URI is set — writes to standin.action_items collection.
    Falls back to stub log when MongoDB is not configured.

    payload: { description: str, owner: str, urgency: str, escalation_required?: bool }
    """
    if not _MONGODB_URI:
        desc = payload.get("description", "")
        _LOGGER.info(f"[STUB] create_action_item | '{desc}' — MONGODB_URI not set")
        return True, f"[stub] Action item '{desc}' would be saved to MongoDB.", True

    try:
        db = _get_db()
        doc = {
            "action_id":           action_id,
            "description":         payload.get("description", ""),
            "owner":               payload.get("owner", "unassigned"),
            "urgency":             payload.get("urgency", "medium"),
            "escalation_required": payload.get("escalation_required", False),
            "priority":            priority,
            "created_at":          datetime.now(UTC).isoformat(),
            "status":              "open",
        }
        db["action_items"].insert_one(doc)
        _LOGGER.info(f"Action item saved | id={action_id}")
        return True, f"Action item saved. id={action_id}", False  # not a stub
    except Exception as exc:
        _LOGGER.warning(f"MongoDB write failed: {exc}")
        return False, f"MongoDB write failed: {exc}", True


async def _action_post_brief(action_id: str, payload: dict, priority: str) -> tuple[bool, str, bool]:
    """
    LIVE when MONGODB_URI is set — persists an Evidence Passport or full brief
    to standin.evidence_passports for the frontend to display.
    Falls back to stub when MongoDB is not configured.

    payload: { brief_id: str, brief_data: dict, escalation_required?: bool }
    """
    if not _MONGODB_URI:
        brief_id = payload.get("brief_id", "unknown")
        _LOGGER.info(f"[STUB] post_brief | brief_id={brief_id} — MONGODB_URI not set")
        return True, f"[stub] Brief '{brief_id}' would be saved to MongoDB.", True

    try:
        db = _get_db()
        doc = {
            "action_id":           action_id,
            "brief_id":            payload.get("brief_id", str(uuid.uuid4())),
            "brief_data":          payload.get("brief_data", {}),
            "escalation_required": payload.get("escalation_required", False),
            "created_at":          datetime.now(UTC).isoformat(),
        }
        db["evidence_passports"].insert_one(doc)
        _LOGGER.info(f"Brief saved | brief_id={doc['brief_id']}")
        return True, f"Brief saved. brief_id={doc['brief_id']}", False
    except Exception as exc:
        _LOGGER.warning(f"MongoDB write failed: {exc}")
        return False, f"MongoDB write failed: {exc}", True


# Action registry
_ACTIONS: dict[str, object] = {
    "send_email":          _action_send_email,
    "send_slack":          _action_send_slack,
    "draft_slack":         _action_draft_slack,
    "create_jira":         _action_create_jira,
    "update_jira_status":  _action_update_jira_status,
    "schedule_meeting":    _action_schedule_meeting,
    "add_calendar_reminder": _action_add_calendar_reminder,
    "read_calendar_events": _action_read_calendar_events,
    "read_calendar_event": _action_read_calendar_events,
    "create_action_item":  _action_create_action_item,
    "post_brief":          _action_post_brief,
}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@agent.on_event("startup")
async def on_startup(ctx: Context):
    mongo_ok = bool(_MONGODB_URI)
    live_actions    = ["create_action_item", "post_brief"] if mongo_ok else []
    stub_actions    = [k for k in _ACTIONS if k not in live_actions]
    ctx.logger.info(
        f"Perform Action online | address={ctx.agent.address} | port={_PORT}"
    )
    ctx.logger.info(
        f"MongoDB: {'connected' if mongo_ok else 'not configured'} | "
        f"Live: {live_actions or 'none'} | "
        f"Approval-gated: none (disabled) | "
        f"Stubs: {stub_actions}"
    )
    if not mongo_ok:
        ctx.logger.warning(
            "MONGODB_URI not set — action logging and live actions "
            "(create_action_item, post_brief) are DISABLED. All actions return stubs."
        )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

@agent.on_message(ActionRequest)
async def handle_action(ctx: Context, sender: str, msg: ActionRequest):
    # NOTE: this agent receives typed uAgents messages, NOT Chat Protocol.
    # Orchestrator must call: await ctx.send(PERFORM_ACTION_ADDRESS, ActionRequest(...))
    ctx.logger.info(
        f"ActionRequest | id={msg.request_id} | type={msg.action_type} | "
        f"priority={msg.priority}"
    )
    try:
        await _handle_action_inner(ctx, sender, msg)
    except Exception as exc:
        ctx.logger.error(f"handle_action crashed: {exc}", exc_info=True)
        await ctx.send(sender, ActionResponse(
            request_id=msg.request_id,
            action_type=msg.action_type,
            success=False,
            action_id=str(uuid.uuid4()),
            error=f"Internal error — action handler crashed. Check agent logs.",
            stub=True,
        ))


async def _handle_action_inner(ctx: Context, sender: str, msg: ActionRequest):
    handler = _ACTIONS.get(msg.action_type)
    if handler is None:
        response = ActionResponse(
            request_id=msg.request_id,
            action_type=msg.action_type,
            success=False,
            action_id=str(uuid.uuid4()),
            error=(
                f"Unknown action_type '{msg.action_type}'. "
                f"Valid types: {list(_ACTIONS.keys())}"
            ),
            stub=True,
        )
        await ctx.send(sender, response)
        return

    try:
        payload = json.loads(msg.payload)
    except json.JSONDecodeError as exc:
        response = ActionResponse(
            request_id=msg.request_id,
            action_type=msg.action_type,
            success=False,
            action_id=str(uuid.uuid4()),
            error=f"Invalid payload JSON: {exc}",
            stub=True,
        )
        await ctx.send(sender, response)
        return

    action_id = str(uuid.uuid4())
    priority  = msg.priority or "normal"

    ok, normalized_payload, validation_error = normalize_action_payload(
        msg.action_type,
        payload,
        {
            "owner": msg.owner,
            "title": msg.title,
            "summary": msg.summary,
            "context": msg.context,
            "priority": msg.priority,
        },
    )
    if not ok:
        response = ActionResponse(
            request_id=msg.request_id,
            action_type=msg.action_type,
            success=False,
            action_id=action_id,
            error=validation_error or "Invalid payload.",
            stub=False,
        )
        await ctx.send(sender, response)
        return

    # ── Immediate execution ────────────────────────────────────────────────
    exec_payload = normalized_payload

    try:
        success, result, stub = await handler(action_id, exec_payload, priority)
    except Exception as exc:
        ctx.logger.error(f"Action '{msg.action_type}' raised unexpectedly: {exc}")
        success, result, stub = False, str(exc), True

    _log_action(action_id, msg.action_type, exec_payload, success, result, stub)

    response = ActionResponse(
        request_id=msg.request_id,
        action_type=msg.action_type,
        success=success,
        action_id=action_id,
        result=result,
        stub=stub,
    )

    ctx.logger.info(
        f"Action done | type={msg.action_type} | success={success} | stub={stub}"
    )
    await ctx.send(sender, response)


# ---------------------------------------------------------------------------
# REST endpoints — human approval UI
# ---------------------------------------------------------------------------

@agent.on_rest_get("/approvals", PendingActionsResponse)
async def list_pending(ctx: Context) -> PendingActionsResponse:
    """Return all actions currently waiting for human approval."""
    if not _MONGODB_URI:
        return PendingActionsResponse(count=0, actions=[])
    try:
        db  = _get_db()
        raw = list(db["pending_approvals"].find(
            {"status": "pending"},
            {"_id": 0},
        ))
        actions = [
            PendingAction(
                action_id=r["action_id"],
                action_type=r["action_type"],
                payload_json=json.dumps(r.get("payload", {})),
                priority=r.get("priority", "normal"),
                created_at=r.get("created_at", ""),
                requested_by=r.get("requested_by"),
                title=r.get("title", r["action_type"].replace("_", " ").title()),
                summary=r.get("summary", ""),
                team=r.get("team", ""),
                owner=r.get("owner", ""),
                owner_name=r.get("owner_name", ""),
                ticket_status=r.get("ticket_status", "in_review"),
                risk=r.get("risk", "medium"),
                stub=r.get("stub", True),
                escalation_json=json.dumps(r.get("escalation", {})),
            )
            for r in raw
        ]
        return PendingActionsResponse(count=len(actions), actions=actions)
    except Exception as exc:
        ctx.logger.error(f"list_pending failed: {exc}")
        return PendingActionsResponse(count=0, actions=[])


@agent.on_rest_post("/approvals/approve", ApproveRequest, ApproveResponse)
async def approve_action(ctx: Context, req: ApproveRequest) -> ApproveResponse:
    """Approve a pending action and execute it immediately."""
    if not _MONGODB_URI:
        return ApproveResponse(
            action_id=req.action_id, action_type="unknown",
            approved=False, error="MONGODB_URI not configured",
        )
    try:
        db  = _get_db()
        doc = db["pending_approvals"].find_one({"action_id": req.action_id, "status": "pending"})
        if not doc:
            return ApproveResponse(
                action_id=req.action_id, action_type="unknown",
                approved=False, error="Action not found or already resolved",
            )

        action_type = doc["action_type"]
        payload     = dict(doc.get("payload") or {})
        priority    = doc.get("priority", "normal")
        handler     = _ACTIONS.get(action_type)

        if handler is None:
            return ApproveResponse(
                action_id=req.action_id, action_type=action_type,
                approved=False, error=f"No handler for '{action_type}'",
            )

        if action_type == "send_slack":
            if not (payload.get("user_id") or "").strip() and (doc.get("owner") or "").strip():
                payload["user_id"] = doc["owner"].strip()

        ok, payload, validation_error = normalize_action_payload(
            action_type,
            payload,
            {
                "owner": doc.get("owner"),
                "title": doc.get("title"),
                "summary": doc.get("summary"),
                "context": "",
                "priority": priority,
            },
        )
        if not ok:
            return ApproveResponse(
                action_id=req.action_id,
                action_type=action_type,
                approved=False,
                error=validation_error or "Invalid payload.",
            )

        success, result, _ = await handler(req.action_id, payload, priority)
        _mark_approval_done(req.action_id, approved=success, result=result)
        _log_action(req.action_id, action_type, payload, success, result, stub=False)

        ctx.logger.info(
            f"Action approved | id={req.action_id} | type={action_type} | "
            f"approver={req.approver} | success={success}"
        )

        # Proactive notifications — high-signal events only
        if success and action_type == "schedule_meeting":
            attendees = payload.get("attendees") or []
            attendee_str = ", ".join(attendees[:3]) + (" +more" if len(attendees) > 3 else "")
            link = payload.get("calendar_html_link") or ""
            _emit_notification(
                kind="meeting.created",
                title=f"Sync scheduled: {payload.get('title') or 'StandIn meeting'}",
                body=f"Attendees: {attendee_str or 'TBD'}" + (f"\n{link}" if link else ""),
                severity="success",
                action_id=req.action_id,
                team=doc.get("team"),
                owner=doc.get("owner"),
                extra={"calendar_html_link": link, "calendar_event_id": payload.get("calendar_event_id")},
            )
        elif success:
            _emit_notification(
                kind="action.executed",
                title=f"{action_type.replace('_', ' ').title()} delivered",
                body=(doc.get("title") or result or "")[:300],
                severity="success",
                action_id=req.action_id,
                team=doc.get("team"),
                owner=doc.get("owner"),
            )
        else:
            _emit_notification(
                kind="action.failed",
                title=f"{action_type.replace('_', ' ').title()} failed",
                body=(result or "Action handler reported failure.")[:300],
                severity="warning",
                action_id=req.action_id,
                team=doc.get("team"),
                owner=doc.get("owner"),
            )

        return ApproveResponse(
            action_id=req.action_id, action_type=action_type,
            approved=success, result=result,
        )
    except Exception as exc:
        ctx.logger.error(f"approve_action failed: {exc}")
        return ApproveResponse(
            action_id=req.action_id, action_type="unknown",
            approved=False, error=str(exc),
        )


@agent.on_rest_post("/approvals/reject", RejectRequest, RejectResponse)
async def reject_action(ctx: Context, req: RejectRequest) -> RejectResponse:
    """Reject a pending action — it will not execute."""
    if not _MONGODB_URI:
        return RejectResponse(action_id=req.action_id, rejected=False)
    try:
        db = _get_db()
        _mark_approval_done(
            req.action_id, approved=False,
            result=f"Rejected: {req.reason or 'no reason given'}",
        )
        ctx.logger.info(
            f"Action rejected | id={req.action_id} | reason={req.reason}"
        )
        try:
            rdoc = db["pending_approvals"].find_one({"action_id": req.action_id}) or {}
        except Exception:
            rdoc = {}
        _emit_notification(
            kind="action.rejected",
            title=f"Action rejected: {rdoc.get('title') or req.action_id[:18]}",
            body=req.reason or "No reason given.",
            severity="info",
            action_id=req.action_id,
            team=rdoc.get("team"),
            owner=rdoc.get("owner"),
        )
        return RejectResponse(action_id=req.action_id, rejected=True)
    except Exception as exc:
        ctx.logger.error(f"reject_action failed: {exc}")
        return RejectResponse(action_id=req.action_id, rejected=False)


# ---------------------------------------------------------------------------
# Dashboard graph endpoint
# ---------------------------------------------------------------------------

def _build_graph_from_hardcoded() -> tuple[list[GraphNode], list[GraphEdge]]:
    """Fallback when MongoDB is not configured — uses company_data directly."""
    nodes = [
        GraphNode(
            id=uid,
            name=u["name"],
            role=u["role"],
            team=u["team"],
            email=u["email"],
            agent_slug=u.get("agent", "") or "",
        )
        for uid, u in USERS.items()
    ]

    raw_edges: list[dict] = []

    for msg in SLACK.values():
        for reply in msg.get("thread", []):
            if reply["sender"] != msg["sender"]:
                raw_edges.append({
                    "from_user": msg["sender"], "to_user": reply["sender"],
                    "type": "slack_thread", "source_id": msg["id"],
                    "label": f"Thread in #{msg['channel']}",
                    "timestamp": reply.get("timestamp", msg["timestamp"]),
                })

    for ticket in JIRA.values():
        reporter, assignee = ticket.get("reporter", ""), ticket.get("assignee", "")
        if reporter and assignee and reporter != assignee:
            raw_edges.append({
                "from_user": reporter, "to_user": assignee,
                "type": "jira", "source_id": ticket["id"],
                "label": ticket["title"][:80],
                "timestamp": ticket.get("created", ""),
            })

    for meeting in CALENDAR.values():
        attendees = meeting.get("attendees", [])
        ts = f"{meeting['date']}T{meeting['time']}:00Z"
        for i, a in enumerate(attendees):
            for b in attendees[i + 1:]:
                raw_edges.append({
                    "from_user": a, "to_user": b,
                    "type": "meeting", "source_id": meeting["id"],
                    "label": meeting["title"], "timestamp": ts,
                })

    # Aggregate weight for repeated pairs
    edge_map: dict[tuple, dict] = {}
    for e in raw_edges:
        key = (e["from_user"], e["to_user"], e["type"], e["source_id"])
        if key in edge_map:
            edge_map[key]["weight"] += 1
        else:
            edge_map[key] = {**e, "weight": 1}

    edges = [GraphEdge(**e) for e in edge_map.values()]
    return nodes, edges


@agent.on_rest_get("/graph", GraphResponse)
async def get_graph(ctx: Context) -> GraphResponse:
    """
    Returns the full user interaction graph for the dashboard UI.

    Nodes  = all users from agent_profiles
    Edges  = meeting co-attendance, Slack thread replies, Jira reporter/assignee

    Falls back to hardcoded company_data when MongoDB is not configured.
    Once real MCP tools are connected, replace hardcoded data with live queries.

    Response shape:
      { nodes: [{id, name, role, team, email}],
        edges: [{from_user, to_user, type, source_id, label, timestamp, weight}],
        generated_at, source }
    """
    from datetime import datetime, UTC
    now = datetime.now(UTC).isoformat()

    if not _MONGODB_URI:
        nodes, edges = _build_graph_from_hardcoded()
        ctx.logger.debug(f"Graph (hardcoded) | {len(nodes)} nodes | {len(edges)} edges")
        return GraphResponse(nodes=nodes, edges=edges, generated_at=now, source="hardcoded")

    try:
        db    = _get_db()
        users = list(db["agent_profiles"].find({}, {"_id": 0}))
        ixs   = list(db["interactions"].find({}, {"_id": 0}))

        nodes = [
            GraphNode(
                id=u.get("agent_id", u.get("id", "")),
                name=u["name"],
                role=u["role"],
                team=u["team"],
                email=u["email"],
                agent_slug=u.get("agent_slug", ""),
            )
            for u in users
        ]

        edge_map: dict[tuple, dict] = {}
        for ix in ixs:
            key = (ix["from_user"], ix["to_user"], ix["type"], ix["source_id"])
            if key in edge_map:
                edge_map[key]["weight"] += 1
            else:
                edge_map[key] = {
                    "from_user": ix["from_user"],
                    "to_user":   ix["to_user"],
                    "type":      ix["type"],
                    "source_id": ix["source_id"],
                    "label":     ix.get("label", ""),
                    "timestamp": ix.get("timestamp", ""),
                    "weight":    1,
                }

        edges = [GraphEdge(**e) for e in edge_map.values()]
        ctx.logger.debug(f"Graph (mongodb) | {len(nodes)} nodes | {len(edges)} edges")
        return GraphResponse(nodes=nodes, edges=edges, generated_at=now, source="mongodb")

    except Exception as exc:
        ctx.logger.warning(f"Graph MongoDB read failed, falling back: {exc}")
        nodes, edges = _build_graph_from_hardcoded()
        return GraphResponse(nodes=nodes, edges=edges, generated_at=now, source="hardcoded")


# ---------------------------------------------------------------------------
# Action log feed endpoint — used by dashboard pipeline trace
# ---------------------------------------------------------------------------

class _ActionSubmitRest(Model):
    """REST shim — same shape as ActionRequest, but tolerates missing request_id."""
    action_type: str
    payload: str
    request_id: str | None = None
    context: str | None = None
    priority: str | None = "normal"
    title: str | None = None
    summary: str | None = None
    team: str | None = None
    owner: str | None = None
    owner_name: str | None = None
    ticket_status: str | None = None
    risk: str | None = "medium"


class _ActionSubmitRestResponse(Model):
    """REST shim response — exposes whether the action queued for approval."""
    action_id: str
    action_type: str
    success: bool
    pending_approval: bool = False
    error: str | None = None
    result: str | None = None


@agent.on_rest_post("/actions", _ActionSubmitRest, _ActionSubmitRestResponse)
async def submit_action(ctx: Context, req: _ActionSubmitRest) -> _ActionSubmitRestResponse:
    """
    Submit a fresh action from the dashboard (e.g. 'Schedule sync' button).
    Approval-gated actions land in standin.pending_approvals; the UI then
    surfaces a card the user must approve before execution.
    """
    request_id = req.request_id or str(uuid.uuid4())

    # Capture the inner handler's outbound ActionResponse via a fake sender.
    captured: dict = {}

    class _CaptureCtx:
        def __init__(self, real):
            self.logger = real.logger
        async def send(self, sender, response):
            captured["resp"] = response

    inner_msg = ActionRequest(
        request_id=request_id,
        action_type=req.action_type,
        payload=req.payload,
        context=req.context,
        priority=req.priority or "normal",
        title=req.title,
        summary=req.summary,
        team=req.team,
        owner=req.owner,
        owner_name=req.owner_name,
        ticket_status=req.ticket_status,
        risk=req.risk or "medium",
    )

    try:
        await _handle_action_inner(_CaptureCtx(ctx), "dashboard", inner_msg)
    except Exception as exc:
        ctx.logger.error(f"submit_action failed: {exc}", exc_info=True)
        return _ActionSubmitRestResponse(
            action_id=request_id,
            action_type=req.action_type,
            success=False,
            error=f"Internal error: {exc}",
        )

    resp: ActionResponse = captured.get("resp")
    if resp is None:
        return _ActionSubmitRestResponse(
            action_id=request_id,
            action_type=req.action_type,
            success=False,
            error="No response from action handler.",
        )
    pending = (resp.result or "").lower().startswith("pending_approval") or \
              (req.action_type in _APPROVAL_REQUIRED)

    if pending and (req.priority or "").lower() == "urgent":
        _emit_notification(
            kind="escalation.opened",
            title=f"Escalation queued: {req.title or req.action_type}",
            body=req.summary or "Awaiting agent resolution.",
            severity="critical",
            action_id=resp.action_id,
            team=req.team,
            owner=req.owner,
        )

    return _ActionSubmitRestResponse(
        action_id=resp.action_id,
        action_type=resp.action_type,
        success=resp.success,
        pending_approval=pending,
        error=resp.error,
        result=resp.result,
    )


@agent.on_rest_get("/log", FeedResponse)
async def get_log(ctx: Context) -> FeedResponse:
    """
    Returns the 30 most-recent action_log entries for the dashboard feed.
    Falls back to empty list when MongoDB is not configured.
    """
    if not _MONGODB_URI:
        return FeedResponse(entries=[], source="fallback")
    try:
        db = _get_db()
        docs = list(
            db["action_log"]
            .find({}, {"_id": 0})
            .sort("created_at", -1)
            .limit(30)
        )
        entries = [
            FeedEntry(
                ts=doc.get("created_at", ""),
                agent="perform_action",
                tool=doc.get("action_type", "unknown"),
                status="DONE" if doc.get("success") else "FAIL",
                stub=bool(doc.get("stub", True)),
                meta=(doc.get("result") or "")[:60],
            )
            for doc in docs
        ]
        return FeedResponse(entries=entries, source="mongodb")
    except Exception as exc:
        ctx.logger.warning(f"log endpoint failed: {exc}")
        return FeedResponse(entries=[], source="fallback")


# ---------------------------------------------------------------------------
# Notifications — proactive feed of high-signal events for the dashboard
# ---------------------------------------------------------------------------
#
# Anything worth interrupting the user about goes here: a meeting got booked,
# an agent conversation resolved, an escalation opened, a watchdog flagged a
# status change. We persist to standin.notifications so the bell icon can
# backfill on page load, and the UI cursor-polls /notifications/list every
# few seconds for live arrivals.

_NOTIFICATIONS_COLL = "notifications"


def _emit_notification(
    kind: str,
    title: str,
    body: str = "",
    severity: str = "info",          # 'info' | 'success' | 'warning' | 'critical'
    action_id: str | None = None,
    conversation_id: str | None = None,
    owner: str | None = None,
    team: str | None = None,
    extra: dict | None = None,
) -> str | None:
    """Insert a notification row. Safe no-op when MongoDB is unavailable."""
    if not _MONGODB_URI:
        return None
    note_id = f"note-{uuid.uuid4().hex[:10]}"
    doc = {
        "id": note_id,
        "ts": datetime.now(UTC).isoformat(),
        "kind": kind,
        "severity": severity,
        "title": title[:160],
        "body": (body or "")[:480],
        "action_id": action_id,
        "conversation_id": conversation_id,
        "owner": owner,
        "team": team,
        "extra": extra or {},
        "read": False,
    }
    try:
        db = _get_db()
        db[_NOTIFICATIONS_COLL].insert_one(dict(doc))
        # Mongo mutates the dict (adds _id) — strip it before logging
        _LOGGER.info(f"notify | {kind} | {severity} | {title[:80]}")
        return note_id
    except Exception as exc:
        _LOGGER.warning(f"notify failed ({kind}): {exc}")
        return None


# ---------------------------------------------------------------------------
# Agent-to-agent resolution conversations
# ---------------------------------------------------------------------------
#
# When the user clicks "Accept" on an attention card, we kick off a simulated
# agent conversation: orchestrator delegates to status / historical / perform
# action, they exchange findings, and converge on a resolution. Messages are
# persisted to MongoDB and streamed to the dashboard via polling.

_CONVERSATIONS_COLL = "agent_conversations"

_AGENT_PROFILES = {
    "orchestrator":     {"label": "Our Orchestrator",        "tone": "orch",     "org": "ours"},
    "status_agent":     {"label": "Status Agent",            "tone": "stat",     "org": "ours"},
    "historical_agent": {"label": "Historical Agent",        "tone": "hist",     "org": "ours"},
    "perform_action":   {"label": "Perform Action",          "tone": "perf",     "org": "ours"},
    "watchdog":         {"label": "Watchdog",                "tone": "watch",    "org": "ours"},
    # Peer agents — represent OTHER users' StandIn agents (cross-org A2A handshake).
    "peer_engineering": {"label": "Engineering · StandIn",   "tone": "peer-eng", "org": "engineering"},
    "peer_design":      {"label": "Design · StandIn",        "tone": "peer-des", "org": "design"},
    "peer_gtm":         {"label": "GTM · StandIn",           "tone": "peer-gtm", "org": "gtm"},
    "peer_product":     {"label": "Product · StandIn",       "tone": "peer-prd", "org": "product"},
}


# Map a team name to its peer agent id (used to pick counterparty for the dialog).
def _peer_for_team(team: str) -> str:
    t = (team or "").strip().lower()
    if t.startswith("eng"):     return "peer_engineering"
    if t.startswith("des"):     return "peer_design"
    if t.startswith("gtm"):     return "peer_gtm"
    if t.startswith("pro"):     return "peer_product"
    return "peer_engineering"


def _conversation_script(action_type: str, title: str, owner: str, team: str, summary: str) -> list[dict]:
    """
    Returns an ordered list of messages: {from, to, kind, content, delay_ms}.

    Models a cross-org agent-to-agent (A2A) negotiation: our user's
    orchestrator opens a channel with the *counterparty user's* StandIn
    orchestrator (e.g. Engineering's StandIn, Design's StandIn). Internal
    helpers (status / historical) chime in only when our orchestrator needs
    grounding, so the dialog reads as peer-to-peer.
    """
    owner_label = owner or "owner"
    team_label  = team or "team"
    title_label = title or action_type.replace("_", " ").title()
    primary_peer = _peer_for_team(team)

    if action_type == "schedule_meeting":
        # Cross-org negotiation between two peer orchestrators
        peer_a = "peer_engineering"
        peer_b = "peer_design"
        return [
            {"from": "orchestrator", "to": peer_a, "kind": "handshake",
             "content": f"Hi — opening A2A channel re: '{title_label}'. Conflict on launch readiness. Are you available to coordinate?", "delay_ms": 700},
            {"from": peer_a, "to": "orchestrator", "kind": "handshake",
             "content": "Acknowledged. Engineering side: NOVA-142 is currently blocked on the /v1 → /v2 contract change pushed last night. Need 15 min to align.", "delay_ms": 1300},
            {"from": "orchestrator", "to": peer_b, "kind": "handshake",
             "content": f"Looping in Design — Engineering is reporting a blocker. You marked the launch page as ready. Can you confirm scope?", "delay_ms": 900},
            {"from": peer_b, "to": "orchestrator", "kind": "finding",
             "content": "Confirming — launch page is shipped and tested against /v1. We can re-test against /v2 but need ~10 min with Eng on the call.", "delay_ms": 1200},
            {"from": "orchestrator", "to": "historical_agent", "kind": "delegate",
             "content": "Has this contract-version mismatch happened before on Launch Alpha? Pull last 14 days.", "delay_ms": 800},
            {"from": "historical_agent", "to": "orchestrator", "kind": "finding",
             "content": "2 prior incidents (NOVA-097, NOVA-118) — both resolved by a 15-min sync between Eng + Design leads. Avg time-to-unblock: 22 min.", "delay_ms": 1200},
            {"from": "orchestrator", "to": peer_a, "kind": "decision",
             "content": "Proposal: 15-min sync, Eng + Design only, in 1 hour. GTM not required at this stage. Confirm?", "delay_ms": 800},
            {"from": peer_a, "to": "orchestrator", "kind": "decision",
             "content": "Confirmed. Derek is free at the proposed slot.", "delay_ms": 1000},
            {"from": peer_b, "to": "orchestrator", "kind": "decision",
             "content": "Confirmed on Design side. Priya will join.", "delay_ms": 900},
            {"from": "orchestrator", "to": "perform_action", "kind": "delegate",
             "content": "All parties agreed. Book the 15-min sync.", "delay_ms": 700},
            {"from": "perform_action", "to": "orchestrator", "kind": "tool_call",
             "content": "calendar.create_event → 15 min · attendees: derek.vasquez@novaloop.io, priya.mehta@novaloop.io", "delay_ms": 1100},
            {"from": "perform_action", "to": "orchestrator", "kind": "completed",
             "content": "Meeting created. Calendar invites sent to both peer agents. Action item logged.", "delay_ms": 900},
        ]

    if action_type in ("send_slack", "draft_slack"):
        peer = primary_peer
        return [
            {"from": "orchestrator", "to": peer, "kind": "handshake",
             "content": f"Opening A2A — need to ping {owner_label} re: '{title_label}'. Are they reachable on your end?", "delay_ms": 700},
            {"from": peer, "to": "orchestrator", "kind": "finding",
             "content": f"{owner_label} is online, active in #launch-alpha. No DND. Safe to ping.", "delay_ms": 1100},
            {"from": "orchestrator", "to": "status_agent", "kind": "delegate",
             "content": "Confirm message context is still valid (status hasn't shifted in last 30 min).", "delay_ms": 700},
            {"from": "status_agent", "to": "orchestrator", "kind": "finding",
             "content": f"{team_label} status unchanged. Context still valid.", "delay_ms": 1000},
            {"from": "orchestrator", "to": peer, "kind": "decision",
             "content": "Sending now — will keep continuity in the existing thread.", "delay_ms": 700},
            {"from": "orchestrator", "to": "perform_action", "kind": "delegate",
             "content": f"Deliver Slack to @{owner_label}.", "delay_ms": 600},
            {"from": "perform_action", "to": "orchestrator", "kind": "tool_call",
             "content": f"slack.post_message → @{owner_label}", "delay_ms": 1000},
            {"from": "perform_action", "to": "orchestrator", "kind": "completed",
             "content": "Slack delivered. Thread linked to evidence passport.", "delay_ms": 800},
        ]

    if action_type == "send_email":
        peer = primary_peer
        return [
            {"from": "orchestrator", "to": peer, "kind": "handshake",
             "content": f"Need to email {owner_label} re: '{title_label}'. Sharing thread context first.", "delay_ms": 700},
            {"from": peer, "to": "orchestrator", "kind": "finding",
             "content": "Acknowledged. Owner has 1 prior thread on this topic — last reply 3 days ago. Continuity recommended.", "delay_ms": 1200},
            {"from": "orchestrator", "to": "perform_action", "kind": "decision",
             "content": "Send as reply on existing thread.", "delay_ms": 700},
            {"from": "perform_action", "to": "orchestrator", "kind": "tool_call",
             "content": f"gmail.send → {owner_label}", "delay_ms": 1100},
            {"from": "perform_action", "to": "orchestrator", "kind": "completed",
             "content": "Email queued. Tracking pixel disabled per policy.", "delay_ms": 800},
        ]

    if action_type in ("create_jira", "update_jira_status"):
        peer = primary_peer
        return [
            {"from": "orchestrator", "to": peer, "kind": "handshake",
             "content": f"Coordinating ticket '{title_label}'. Confirm scope on your side?", "delay_ms": 700},
            {"from": peer, "to": "orchestrator", "kind": "finding",
             "content": f"Scope confirmed. Owner = {owner_label}. Priority matches current Q126SPRINT.", "delay_ms": 1100},
            {"from": "orchestrator", "to": "perform_action", "kind": "decision",
             "content": "Update ticket in Q126SPRINT.", "delay_ms": 700},
            {"from": "perform_action", "to": "orchestrator", "kind": "tool_call",
             "content": "jira.transition → Q126SPRINT", "delay_ms": 1000},
            {"from": "perform_action", "to": "orchestrator", "kind": "completed",
             "content": "Jira updated. Linked back to evidence passport.", "delay_ms": 800},
        ]

    # generic fallback
    peer = primary_peer
    return [
        {"from": "orchestrator", "to": peer, "kind": "handshake",
         "content": f"Opening A2A — need to align on '{title_label}'. Ready?", "delay_ms": 700},
        {"from": peer, "to": "orchestrator", "kind": "finding",
         "content": f"Ready. {summary[:140] or 'No new blockers on our side.'}", "delay_ms": 1100},
        {"from": "orchestrator", "to": "perform_action", "kind": "decision",
         "content": "Proceed with the action as queued.", "delay_ms": 700},
        {"from": "perform_action", "to": "orchestrator", "kind": "tool_call",
         "content": f"{action_type} → executing", "delay_ms": 1000},
        {"from": "perform_action", "to": "orchestrator", "kind": "completed",
         "content": "Done. Logged to action_log.", "delay_ms": 800},
    ]


def _conv_now() -> str:
    return datetime.now(UTC).isoformat()


def _conv_init_doc(conversation_id: str, action_id: str, action_type: str,
                   title: str, owner: str, team: str, summary: str,
                   participants: list[str]) -> dict:
    return {
        "conversation_id": conversation_id,
        "action_id": action_id,
        "action_type": action_type,
        "title": title,
        "owner": owner,
        "team": team,
        "summary": summary,
        "topic": title or action_type.replace("_", " ").title(),
        "status": "running",
        "started_at": _conv_now(),
        "updated_at": _conv_now(),
        "participants": participants,
        "messages": [],
    }


async def _run_conversation(conversation_id: str, script: list[dict], action_id: str) -> None:
    """
    Background task: stream messages into MongoDB on a realistic cadence,
    then mark the conversation resolved and approve the underlying action.
    """
    if not _MONGODB_URI:
        return
    try:
        db = _get_db()
        coll = db[_CONVERSATIONS_COLL]
    except Exception as exc:
        _LOGGER.warning(f"conversation runner: db unavailable ({exc})")
        return

    for i, step in enumerate(script):
        await asyncio.sleep(max(step.get("delay_ms", 800), 300) / 1000.0)
        msg = {
            "id": f"m-{i+1:02d}",
            "ts": _conv_now(),
            "from": step["from"],
            "to":   step["to"],
            "kind": step["kind"],
            "content": step["content"],
        }
        try:
            coll.update_one(
                {"conversation_id": conversation_id},
                {"$push": {"messages": msg}, "$set": {"updated_at": _conv_now()}},
            )
        except Exception as exc:
            _LOGGER.warning(f"conversation push failed: {exc}")
            return

    # Mark resolved + approve underlying pending action (if any)
    try:
        conv_doc = coll.find_one({"conversation_id": conversation_id}, {"_id": 0})
        coll.update_one(
            {"conversation_id": conversation_id},
            {"$set": {"status": "resolved", "updated_at": _conv_now()}},
        )
        if action_id:
            db["pending_approvals"].update_one(
                {"action_id": action_id, "status": "pending"},
                {"$set": {"status": "approved", "approved_at": _conv_now(),
                          "approved_by": "agent_conversation"}},
            )
        topic = (conv_doc or {}).get("topic") or "ticket"
        action_type = (conv_doc or {}).get("action_type") or ""
        _emit_notification(
            kind="conversation.resolved",
            title=f"Agents resolved: {topic}",
            body=f"Cross-agent conversation reached a decision via {action_type or 'agent_handoff'}.",
            severity="success",
            action_id=action_id,
            conversation_id=conversation_id,
            team=(conv_doc or {}).get("team"),
            owner=(conv_doc or {}).get("owner"),
        )
    except Exception as exc:
        _LOGGER.warning(f"conversation finalize failed: {exc}")


class _ConvStartReq(Model):
    action_id: str
    action_type: str = ""
    title: str = ""
    owner: str = ""
    team: str = ""
    summary: str = ""


class _ConvMessage(Model):
    id: str
    ts: str
    sender: str
    recipient: str
    kind: str
    content: str


class _ConvState(Model):
    conversation_id: str
    action_id: str
    action_type: str
    topic: str
    status: str  # 'running' | 'resolved' | 'failed' | 'unknown'
    started_at: str
    updated_at: str
    participants: List[str]
    messages: List[_ConvMessage]


class _ConvStartResp(Model):
    conversation_id: str
    action_id: str
    status: str
    error: Optional[str] = None


class _ConvGetReq(Model):
    conversation_id: str


@agent.on_rest_post("/conversations/start", _ConvStartReq, _ConvStartResp)
async def start_conversation(ctx: Context, req: _ConvStartReq) -> _ConvStartResp:
    """Kick off an agent-to-agent conversation to resolve an attention card."""
    if not _MONGODB_URI:
        return _ConvStartResp(
            conversation_id="", action_id=req.action_id, status="failed",
            error="MONGODB_URI not configured",
        )

    action_type = req.action_type or "generic"
    title       = req.title or ""
    owner       = req.owner or ""
    team        = req.team or ""
    summary     = req.summary or ""

    # If caller didn't supply, look up the pending action.
    try:
        db = _get_db()
        if not action_type or not title:
            doc = db["pending_approvals"].find_one({"action_id": req.action_id})
            if doc:
                action_type = action_type or doc.get("action_type", "generic")
                title       = title       or doc.get("title", "")
                owner       = owner       or doc.get("owner", "")
                team        = team        or doc.get("team", "")
                summary     = summary     or doc.get("summary", "")
    except Exception as exc:
        ctx.logger.warning(f"start_conversation lookup failed: {exc}")

    script       = _conversation_script(action_type, title, owner, team, summary)
    participants = sorted({s["from"] for s in script} | {s["to"] for s in script})
    conversation_id = f"conv-{uuid.uuid4().hex[:10]}"

    try:
        db = _get_db()
        db[_CONVERSATIONS_COLL].insert_one(
            _conv_init_doc(
                conversation_id, req.action_id, action_type,
                title, owner, team, summary, participants,
            )
        )
    except Exception as exc:
        ctx.logger.error(f"start_conversation insert failed: {exc}")
        return _ConvStartResp(
            conversation_id="", action_id=req.action_id, status="failed",
            error=str(exc),
        )

    asyncio.create_task(_run_conversation(conversation_id, script, req.action_id))
    ctx.logger.info(
        f"Conversation started | id={conversation_id} | action={req.action_id} | "
        f"type={action_type} | steps={len(script)}"
    )
    return _ConvStartResp(
        conversation_id=conversation_id, action_id=req.action_id, status="running",
    )


def _conv_doc_to_state(doc: dict) -> _ConvState:
    msgs = [
        _ConvMessage(
            id=m.get("id", ""),
            ts=m.get("ts", ""),
            sender=m.get("from", ""),
            recipient=m.get("to", ""),
            kind=m.get("kind", "message"),
            content=m.get("content", ""),
        )
        for m in (doc.get("messages") or [])
    ]
    return _ConvState(
        conversation_id=doc.get("conversation_id", ""),
        action_id=doc.get("action_id", ""),
        action_type=doc.get("action_type", ""),
        topic=doc.get("topic", ""),
        status=doc.get("status", "unknown"),
        started_at=doc.get("started_at", ""),
        updated_at=doc.get("updated_at", ""),
        participants=list(doc.get("participants") or []),
        messages=msgs,
    )


@agent.on_rest_post("/conversations/get", _ConvGetReq, _ConvState)
async def get_conversation(ctx: Context, req: _ConvGetReq) -> _ConvState:
    """Return the current state (messages + status) of a conversation."""
    if not _MONGODB_URI:
        return _ConvState(
            conversation_id=req.conversation_id, action_id="", action_type="",
            topic="", status="unknown", started_at="", updated_at="",
            participants=[], messages=[],
        )
    try:
        db = _get_db()
        doc = db[_CONVERSATIONS_COLL].find_one(
            {"conversation_id": req.conversation_id}, {"_id": 0},
        )
        if not doc:
            return _ConvState(
                conversation_id=req.conversation_id, action_id="", action_type="",
                topic="", status="unknown", started_at="", updated_at="",
                participants=[], messages=[],
            )
        return _conv_doc_to_state(doc)
    except Exception as exc:
        ctx.logger.error(f"get_conversation failed: {exc}")
        return _ConvState(
            conversation_id=req.conversation_id, action_id="", action_type="",
            topic="", status="failed", started_at="", updated_at="",
            participants=[], messages=[],
        )


# ---------------------------------------------------------------------------
# Notifications — REST endpoints
# ---------------------------------------------------------------------------


class _NotificationItem(Model):
    id: str
    ts: str
    kind: str
    severity: str
    title: str
    body: str
    action_id: Optional[str] = None
    conversation_id: Optional[str] = None
    owner: Optional[str] = None
    team: Optional[str] = None
    read: bool = False


class _NotifListReq(Model):
    since: Optional[str] = None  # ISO timestamp; only newer than this
    limit: int = 30
    include_read: bool = True


class _NotifListResp(Model):
    notifications: List[_NotificationItem]
    unread_count: int
    cursor: str  # latest ts in this batch (or echo `since` if empty)


class _NotifMarkReadReq(Model):
    ids: List[str] = []
    all: bool = False


class _NotifMarkReadResp(Model):
    updated: int


@agent.on_rest_post("/notifications/list", _NotifListReq, _NotifListResp)
async def list_notifications(ctx: Context, req: _NotifListReq) -> _NotifListResp:
    """Return notifications newer than `since` (ISO ts). Use returned `cursor`
    for the next call to avoid duplicates. Falls back gracefully when Mongo
    is unconfigured."""
    if not _MONGODB_URI:
        return _NotifListResp(notifications=[], unread_count=0, cursor=req.since or "")
    try:
        db = _get_db()
        coll = db[_NOTIFICATIONS_COLL]

        query: dict = {}
        if req.since:
            query["ts"] = {"$gt": req.since}
        if not req.include_read:
            query["read"] = False

        limit = max(1, min(int(req.limit or 30), 100))
        docs = list(
            coll.find(query, {"_id": 0})
                .sort("ts", -1)
                .limit(limit)
        )

        items = [
            _NotificationItem(
                id=d.get("id", ""),
                ts=d.get("ts", ""),
                kind=d.get("kind", "unknown"),
                severity=d.get("severity", "info"),
                title=d.get("title", ""),
                body=d.get("body", ""),
                action_id=d.get("action_id"),
                conversation_id=d.get("conversation_id"),
                owner=d.get("owner"),
                team=d.get("team"),
                read=bool(d.get("read", False)),
            )
            for d in docs
        ]
        unread_count = coll.count_documents({"read": False})
        cursor = items[0].ts if items else (req.since or "")
        return _NotifListResp(notifications=items, unread_count=unread_count, cursor=cursor)
    except Exception as exc:
        ctx.logger.warning(f"list_notifications failed: {exc}")
        return _NotifListResp(notifications=[], unread_count=0, cursor=req.since or "")


@agent.on_rest_post("/notifications/mark_read", _NotifMarkReadReq, _NotifMarkReadResp)
async def mark_notifications_read(ctx: Context, req: _NotifMarkReadReq) -> _NotifMarkReadResp:
    """Mark specific notifications (or all) as read."""
    if not _MONGODB_URI:
        return _NotifMarkReadResp(updated=0)
    try:
        db = _get_db()
        coll = db[_NOTIFICATIONS_COLL]
        if req.all:
            res = coll.update_many({"read": False}, {"$set": {"read": True}})
        elif req.ids:
            res = coll.update_many({"id": {"$in": list(req.ids)}}, {"$set": {"read": True}})
        else:
            return _NotifMarkReadResp(updated=0)
        return _NotifMarkReadResp(updated=int(getattr(res, "modified_count", 0)))
    except Exception as exc:
        ctx.logger.warning(f"mark_notifications_read failed: {exc}")
        return _NotifMarkReadResp(updated=0)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class _HealthResponse(Model):
    status: str
    agent: str
    mongodb: str
    timestamp: str


@agent.on_rest_get("/health", _HealthResponse)
async def health(ctx: Context) -> _HealthResponse:
    return _HealthResponse(
        status="ok",
        agent="perform_action",
        mongodb="configured" if _MONGODB_URI else "not configured",
        timestamp=datetime.now(UTC).isoformat(),
    )


if __name__ == "__main__":
    agent.run()

