"""
StandIn Orchestrator — Chat Protocol entrypoint.

Only the orchestrator should be Agentverse-facing. Downstream agents are
treated as local workers reached over direct uAgents addresses.
"""

import asyncio
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime

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

# Local sub-agent defaults from deterministic seeds; env values override.
STATUS_AGENT_ADDRESS = os.getenv("STATUS_AGENT_ADDRESS")
HISTORICAL_AGENT_ADDRESS = os.getenv("HISTORICAL_AGENT_ADDRESS")
PERFORM_ACTION_ADDRESS = os.getenv("PERFORM_ACTION_ADDRESS")

chat_proto = Protocol(spec=chat_protocol_spec)
pending_requests: dict[str, dict] = {}
status_sessions: dict[str, str] = {}

TEAM_ALIASES = {
    "engineering": "Engineering",
    "eng": "Engineering",
    "product": "Product",
    "pm": "Product",
    "design": "Design",
    "gtm": "GTM",
    "marketing": "GTM",
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
        payload["text"] = text
    elif action_type == "send_email":
        payload.update({"to": [], "subject": "StandIn request", "body": text})
    elif action_type == "create_jira":
        payload.update({"project": "NOVA", "summary": text[:120], "description": text})
    elif action_type == "update_jira_status":
        ticket = re.search(r"\b([A-Z]{2,10}-\d+)\b", text)
        payload.update({"ticket_id": ticket.group(1) if ticket else "", "new_status": "In Progress", "comment": text})
    elif action_type == "schedule_meeting":
        payload.update({"title": "StandIn follow-up", "attendees": [], "description": text})
    elif action_type == "create_action_item":
        payload.update({"description": text, "owner": "unassigned", "urgency": "medium"})
    elif action_type == "post_brief":
        payload.update({"brief_id": str(uuid.uuid4()), "brief_data": {"summary": text}})
    return payload


async def _classify(text: str) -> IntentClassification:
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


def _format_status_response(msg: FullBriefResponse, intent: str) -> str:
    lines = [f"Status mode: {msg.mode}", f"Overall confidence: {msg.overall_confidence:.2f}", ""]
    lines.append("Role summaries:")
    for role_status in msg.role_statuses:
        blockers = "; ".join(role_status.blockers) if role_status.blockers else "none"
        lines.append(f"- {role_status.role}: {role_status.summary}")
        lines.append(f"  Blockers: {blockers}")
    if intent == "conflict_check":
        lines.extend(["", "Contradictions:"])
        for entry in (msg.contradictions or ["No explicit contradictions found."]):
            lines.append(f"- {entry}")
    else:
        lines.extend(["", f"Recommended action: {msg.recommended_action}"])
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


async def _send_reply(ctx: Context, recipient: str, text: str) -> None:
    await ctx.send(
        recipient,
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid.uuid4(),
            content=[TextContent(type="text", text=text), EndSessionContent(type="end-session")],
        ),
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id))
    user_text = "".join(item.text for item in msg.content if isinstance(item, TextContent)).strip()
    if not user_text:
        await _send_reply(ctx, sender, "I did not receive any text to route.")
        return

    classification = await _classify(user_text)
    request_id = str(uuid.uuid4())
    pending_requests[request_id] = {"sender": sender, "intent": classification.intent}

    if classification.intent in ("status_query", "conflict_check", "briefing_request"):
        await ctx.send(
            STATUS_AGENT_ADDRESS,
            FullBriefRequest(
                request_id=request_id,
                user_email=sender,
                topic=classification.topic,
                roles=classification.teams or None,
                context=user_text,
                session_id=status_sessions.get(sender),
            ),
        )
        return

    if classification.intent == "history_query":
        await ctx.send(
            HISTORICAL_AGENT_ADDRESS,
            RAGRequest(
                request_id=request_id,
                question=user_text,
                role_filter=classification.teams[0] if classification.teams else None,
                top_k=5,
            ),
        )
        return

    if classification.intent == "action_request":
        action_type = classification.action_type or _infer_action_type(user_text)
        if not action_type:
            pending_requests.pop(request_id, None)
            await _send_reply(ctx, sender, "I could not determine which action to run.")
            return
        await ctx.send(
            PERFORM_ACTION_ADDRESS,
            ActionRequest(
                request_id=request_id,
                action_type=action_type,
                payload=classification.action_payload_json or json.dumps(_infer_action_payload(user_text, action_type)),
                context=user_text,
                priority="normal",
            ),
        )
        return

    pending_requests.pop(request_id, None)
    await _send_reply(ctx, sender, "I could not classify that request.")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    _ = ctx
    _ = sender
    _ = msg


@orchestrator.on_message(FullBriefResponse)
async def handle_status_response(ctx: Context, sender: str, msg: FullBriefResponse):
    _ = sender
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        return
    status_sessions[pending["sender"]] = msg.session_id or status_sessions.get(pending["sender"], "")
    await _send_reply(ctx, pending["sender"], _format_status_response(msg, pending["intent"]))


@orchestrator.on_message(RAGResponse)
async def handle_history_response(ctx: Context, sender: str, msg: RAGResponse):
    _ = sender
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        return
    await _send_reply(ctx, pending["sender"], _format_history_response(msg))


@orchestrator.on_message(ActionResponse)
async def handle_action_response(ctx: Context, sender: str, msg: ActionResponse):
    _ = sender
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        return
    await _send_reply(ctx, pending["sender"], _format_action_response(msg))


orchestrator.include(chat_proto, publish_manifest=True)


@orchestrator.on_event("startup")
async def on_startup(ctx: Context):
    ctx.logger.info(f"Orchestrator started: {ctx.agent.address}")
    ctx.logger.info(f"Status Agent:     {STATUS_AGENT_ADDRESS}")
    ctx.logger.info(f"Historical Agent: {HISTORICAL_AGENT_ADDRESS}")
    ctx.logger.info(f"Perform Action:   {PERFORM_ACTION_ADDRESS}")
    if _AGENTVERSE:
        ctx.logger.info("Agentverse enabled for orchestrator only.")


if __name__ == "__main__":
    if _ENDPOINT:
        print(f"Orchestrator endpoint: {_ENDPOINT}")
    if _AGENTVERSE:
        print(f"Agentverse URL: {_AGENTVERSE}")
    orchestrator.run()
