"""
Watchdog Agent — StandIn  (port 8010)

Proactive monitor: polls status_agent on a timer, compares the result
against the last stored brief, and fires a notification via perform_action
when something significant changes.

This is the difference between a tool (answers when asked) and an assistant
(tells you when something breaks without being asked).

Change signals detected:
  - Any role status change  (e.g. ready → blocked)
  - New blocker added
  - Escalation newly required
  - Overall confidence drop > 0.10

Run: python backend/agents/watchdog_agent/agent.py

Required .env:
  STATUS_AGENT_ADDRESS=agent1q...    (copy from status_agent startup log)
  PERFORM_ACTION_ADDRESS=agent1q...  (copy from perform_action startup log)
  WATCHDOG_ALERT_CHANNEL=#standin-alerts   (optional, default #standin-alerts)
  WATCHDOG_INTERVAL_SECONDS=1800          (optional, default 1800 = 30 min)
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, UTC

from dotenv import load_dotenv
from uagents import Agent, Context

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

from models import (
    ActionRequest,
    ActionResponse,
    FullBriefRequest,
    FullBriefResponse,
    WatchdogAlert,
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
_SEED     = os.getenv("WATCHDOG_SEED", "watchdog_standin_seed_v1")
_PORT     = int(os.getenv("WATCHDOG_PORT", "8010"))
_INTERVAL = float(os.getenv("WATCHDOG_INTERVAL_SECONDS", "1800"))

_STATUS_AGENT_ADDRESS  = os.getenv("STATUS_AGENT_ADDRESS", "")
_PERFORM_ACTION_ADDRESS = os.getenv("PERFORM_ACTION_ADDRESS", "")
_ALERT_CHANNEL         = os.getenv("WATCHDOG_ALERT_CHANNEL", "#standin-alerts")
_MONGODB_URI           = os.getenv("MONGODB_URI", "")
_WATCHDOG_EMAIL        = "watchdog@standin.ai"

agent = Agent(
    name="watchdog_agent",
    seed=_SEED,
    port=_PORT,
    mailbox=True,
    publish_agent_details=True,
)

# Tracks in-flight check requests so we can match responses
_pending_checks: dict[str, datetime] = {}


# ---------------------------------------------------------------------------
# MongoDB — load/save snapshot
# ---------------------------------------------------------------------------

def _get_db():
    if not _MONGODB_URI:
        raise RuntimeError("MONGODB_URI not set")
    from pymongo import MongoClient
    client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _load_snapshot() -> dict | None:
    if not _MONGODB_URI:
        return None
    try:
        db = _get_db()
        return db["watchdog_snapshots"].find_one(
            {}, {"_id": 0}, sort=[("saved_at", -1)]
        )
    except Exception:
        return None


def _save_snapshot(brief: FullBriefResponse) -> None:
    if not _MONGODB_URI:
        return
    try:
        db = _get_db()
        db["watchdog_snapshots"].insert_one({
            "request_id":          brief.request_id,
            "overall_confidence":  brief.overall_confidence,
            "escalation_required": brief.escalation_required,
            "role_statuses": [
                {
                    "role":       r.role,
                    "status":     r.status,
                    "blockers":   r.blockers,
                    "confidence": r.confidence,
                }
                for r in brief.role_statuses
            ],
            "saved_at": datetime.now(UTC).isoformat(),
        })
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def _compare_snapshots(
    current: FullBriefResponse,
    previous: dict,
) -> list[str]:
    """Return list of human-readable change descriptions."""
    changes: list[str] = []

    prev_roles = {r["role"]: r for r in previous.get("role_statuses", [])}

    for r in current.role_statuses:
        prev = prev_roles.get(r.role)
        if not prev:
            continue

        if prev.get("status") != r.status:
            changes.append(
                f"[{r.role}] Status changed: {prev.get('status')} → {r.status}"
            )

        prev_blockers = set(prev.get("blockers", []))
        curr_blockers = set(r.blockers)
        for b in curr_blockers - prev_blockers:
            changes.append(f"[{r.role}] New blocker: \"{b[:80]}\"")
        for b in prev_blockers - curr_blockers:
            changes.append(f"[{r.role}] Blocker resolved: \"{b[:80]}\"")

        conf_drop = prev.get("confidence", 1.0) - r.confidence
        if conf_drop > 0.10:
            changes.append(
                f"[{r.role}] Confidence dropped "
                f"{prev.get('confidence', '?'):.2f} → {r.confidence:.2f}"
            )

    # Escalation newly triggered
    if current.escalation_required and not previous.get("escalation_required"):
        changes.append(
            f"Escalation newly required: {current.escalation_reason}"
        )

    # Overall confidence drop
    prev_conf = previous.get("overall_confidence", 1.0)
    curr_conf = current.overall_confidence
    if prev_conf - curr_conf > 0.10:
        changes.append(
            f"Overall confidence dropped {prev_conf:.2f} → {curr_conf:.2f}"
        )

    return changes


# ---------------------------------------------------------------------------
# Interval — trigger a status poll
# ---------------------------------------------------------------------------

@agent.on_interval(period=_INTERVAL)
async def poll_status(ctx: Context) -> None:
    if not _STATUS_AGENT_ADDRESS:
        ctx.logger.warning("STATUS_AGENT_ADDRESS not set — watchdog idle")
        return

    # Drop checks that never got a response (status_agent down or restarted)
    cutoff = datetime.now(UTC) - timedelta(seconds=_INTERVAL * 2)
    stale_ids = [k for k, v in _pending_checks.items() if v < cutoff]
    for k in stale_ids:
        ctx.logger.warning(f"Watchdog check {k} never received a response — dropping")
        del _pending_checks[k]

    req_id = str(uuid.uuid4())
    _pending_checks[req_id] = datetime.now(UTC)

    await ctx.send(
        _STATUS_AGENT_ADDRESS,
        FullBriefRequest(
            request_id=req_id,
            user_email=_WATCHDOG_EMAIL,
            topic="watchdog periodic check",
        ),
    )
    ctx.logger.info(f"Watchdog poll sent | req_id={req_id}")


# ---------------------------------------------------------------------------
# Response handler — compare and alert if needed
# ---------------------------------------------------------------------------

@agent.on_message(FullBriefResponse)
async def handle_brief_response(ctx: Context, sender: str, msg: FullBriefResponse) -> None:
    if msg.request_id not in _pending_checks:
        # Not a watchdog-initiated brief — ignore
        return

    sent_at = _pending_checks.pop(msg.request_id)
    latency = (datetime.now(UTC) - sent_at).total_seconds()
    ctx.logger.info(
        f"Watchdog response received | latency={latency:.1f}s | "
        f"escalation={msg.escalation_required} | "
        f"confidence={msg.overall_confidence:.2f}"
    )

    previous = _load_snapshot()
    _save_snapshot(msg)

    if previous is None:
        ctx.logger.info("No prior snapshot — baseline saved, no alert sent.")
        return

    changes = _compare_snapshots(msg, previous)

    if not changes:
        ctx.logger.info("No significant changes detected.")
        return

    # Build alert message
    ctx.logger.info(f"Changes detected: {len(changes)} — sending alert")
    alert_text = (
        f"*StandIn Watchdog Alert* — {len(changes)} change(s) detected\n\n"
        + "\n".join(f"• {c}" for c in changes)
        + f"\n\nCurrent status: escalation={'YES' if msg.escalation_required else 'no'}, "
        f"confidence={msg.overall_confidence:.2f}"
        + f"\nRecommended action: {msg.recommended_action}"
    )

    if not _PERFORM_ACTION_ADDRESS:
        ctx.logger.warning(f"PERFORM_ACTION_ADDRESS not set — alert not sent:\n{alert_text}")
        return

    # Send via perform_action → draft_slack (creates a draft, not live message,
    # so the approval gate doesn't block it)
    await ctx.send(
        _PERFORM_ACTION_ADDRESS,
        ActionRequest(
            request_id=str(uuid.uuid4()),
            action_type="draft_slack",
            payload=json.dumps({
                "channel": _ALERT_CHANNEL,
                "text":    alert_text,
            }),
            context="watchdog_alert",
            priority="urgent" if msg.escalation_required else "normal",
        ),
    )


@agent.on_message(ActionResponse)
async def handle_action_response(ctx: Context, sender: str, msg: ActionResponse) -> None:
    ctx.logger.info(
        f"Alert action result | type={msg.action_type} | "
        f"success={msg.success} | result={msg.result}"
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(
        f"Watchdog Agent online | address={ctx.agent.address} | port={_PORT}"
    )
    ctx.logger.info(
        f"Polling every {_INTERVAL}s | "
        f"status_agent={'configured' if _STATUS_AGENT_ADDRESS else 'NOT SET — add STATUS_AGENT_ADDRESS to .env'} | "
        f"perform_action={'configured' if _PERFORM_ACTION_ADDRESS else 'NOT SET'} | "
        f"alert_channel={_ALERT_CHANNEL}"
    )
    snapshot = _load_snapshot()
    ctx.logger.info(
        f"Last snapshot: {snapshot.get('saved_at', 'none') if snapshot else 'none'}"
    )


if __name__ == "__main__":
    agent.run()

