"""
Chat Protocol orchestrator for StandIn.

Invoked by ASI:One / Agentverse and routes requests to:
- status_agent       for status, conflict, and briefing intents
- historical_agent   for historical questions
- perform_action     for action requests
"""

import json
import logging
import os
import re
import sys
import uuid
import asyncio
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from agents.historical_agent.agent import agent as historical_agent
from agents.perform_action.agent import agent as perform_action_agent
from agents.status_agent.agent import agent as status_agent
from models import (
    ActionRequest,
    ActionResponse,
    FullBriefRequest,
    FullBriefResponse,
    IntentClassification,
    RAGRequest,
    RAGResponse,
)

_SEED = os.getenv("ORCHESTRATOR_SEED", "standin_orchestrator_seed_v1")
_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8001"))
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_LOGGER = logging.getLogger("standin_orchestrator")

# Gemini client — created once to reuse TCP/TLS connection across all calls
_GEMINI_CLIENT = None


def _get_gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None and _GEMINI_KEY:
        from google import genai
        _GEMINI_CLIENT = genai.Client(api_key=_GEMINI_KEY)
    return _GEMINI_CLIENT


def _normalize_submit_endpoint(raw_endpoint: str | None, port: int) -> str | None:
    if not raw_endpoint:
        return None
    endpoint = raw_endpoint.rstrip("/")
    if endpoint.endswith("/submit"):
        return endpoint
    return f"{endpoint}/submit"


_ENDPOINT = _normalize_submit_endpoint(
    os.getenv("ORCHESTRATOR_ENDPOINT") or os.getenv("PUBLIC_BASE_URL"),
    _PORT,
)
_AGENTVERSE = (os.getenv("AGENTVERSE_URL") or "").rstrip("/") or None

orchestrator = Agent(
    name="standin_orchestrator",
    seed=_SEED,
    port=_PORT,
    endpoint=[_ENDPOINT] if _ENDPOINT else None,
    agentverse=_AGENTVERSE,
    mailbox=False,
    publish_agent_details=True,
)

chat_protocol = Protocol(spec=chat_protocol_spec)

STATUS_AGENT_ADDRESS = os.getenv("STATUS_AGENT_ADDRESS", status_agent.address)
HISTORICAL_AGENT_ADDRESS = os.getenv("HISTORICAL_AGENT_ADDRESS", historical_agent.address)
PERFORM_ACTION_ADDRESS = os.getenv("PERFORM_ACTION_ADDRESS", perform_action_agent.address)

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
    "schedule_meeting": ("schedule", "meeting", "calendar", "invite"),
    "create_action_item": ("action item", "todo", "task"),
    "post_brief": ("post brief", "save brief", "publish brief"),
}

pending_requests: dict[str, dict] = {}
status_sessions: dict[str, str] = {}

_CLASSIFIER_PROMPT = """
You classify user requests for a coordination orchestrator.

Return strict JSON with this schema:
{
  "intent": "status_query|conflict_check|action_request|history_query|briefing_request",
  "teams": ["Engineering" | "Design" | "GTM" | "Product"],
  "topic": "short topic or null",
  "time_window": "short time window phrase or null",
  "action_type": "send_email|send_slack|draft_slack|create_jira|update_jira_status|schedule_meeting|create_action_item|post_brief|null",
  "action_payload_json": "JSON string for action payload or null",
  "confidence": 0.0
}

Rules:
- status_query   = current state / readiness / blockers for a team or project
- conflict_check = contradictions, disagreements, inconsistencies between teams
- briefing_request = broad cross-team summary / executive brief
- history_query  = past decisions, previous meetings, what happened before,
                   OR any lookup about a specific person, ticket, or entity
                   (e.g. "anything about Derek", "what is Alice working on", "tell me about NOVA-142")
- action_request = asks to send/create/update/schedule/post something
- teams: only populate when a team name is explicitly mentioned. Leave [] for person/entity lookups
  — the RAG pipeline will find the relevant documents via vector search.
- Keep topic short and literal.
- time_window should only be set when clearly present.
- action_payload_json must be a compact JSON object string when action_request.
""".strip()


def _extract_text(msg: ChatMessage) -> str:
    chunks: list[str] = []
    for item in msg.content:
        if isinstance(item, TextContent):
            chunks.append(item.text)
    return " ".join(chunks).strip()


def _detect_teams(text: str) -> list[str]:
    lowered = text.lower()
    teams: list[str] = []
    for alias, canonical in TEAM_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered) and canonical not in teams:
            teams.append(canonical)
    return teams


def _extract_time_window(text: str) -> str | None:
    lowered = text.lower()
    for token in (
        "today",
        "tomorrow",
        "yesterday",
        "this week",
        "last week",
        "this month",
        "last month",
        "this quarter",
        "last quarter",
    ):
        if token in lowered:
            return token
    match = re.search(
        r"\b(?:\d{1,2}(?::\d{2})?\s?(?:am|pm)|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        lowered,
    )
    return match.group(0) if match else None


def _infer_action_type(text: str) -> str | None:
    lowered = text.lower()
    for action_type, hints in ACTION_HINTS.items():
        if any(hint in lowered for hint in hints):
            if action_type == "send_slack" and "draft" in lowered:
                continue
            return action_type
    return None


def _infer_action_payload(text: str, action_type: str | None) -> dict:
    payload: dict[str, object] = {"original_request": text}
    if not action_type:
        return payload

    if action_type in {"send_slack", "draft_slack"}:
        channel_match = re.search(r"(#\w[\w-]*)", text)
        payload["channel"] = channel_match.group(1) if channel_match else "#general"
        payload["text"] = text
    elif action_type == "send_email":
        payload["to"] = []
        payload["subject"] = "StandIn request"
        payload["body"] = text
    elif action_type == "create_jira":
        payload["project"] = "NOVA"
        payload["summary"] = text[:120]
        payload["description"] = text
    elif action_type == "update_jira_status":
        ticket_match = re.search(r"\b([A-Z]{2,10}-\d+)\b", text)
        payload["ticket_id"] = ticket_match.group(1) if ticket_match else ""
        payload["new_status"] = "In Progress"
        payload["comment"] = text
    elif action_type == "schedule_meeting":
        payload["title"] = "StandIn follow-up"
        payload["attendees"] = []
        payload["start_time"] = _extract_time_window(text) or ""
        payload["duration_minutes"] = 30
        payload["description"] = text
    elif action_type == "create_action_item":
        payload["description"] = text
        payload["owner"] = "unassigned"
        payload["urgency"] = "medium"
    elif action_type == "post_brief":
        payload["brief_id"] = str(uuid.uuid4())
        payload["brief_data"] = {"summary": text}
    return payload


def _fallback_classification(text: str) -> IntentClassification:
    lowered = text.lower()
    teams = _detect_teams(text)
    time_window = _extract_time_window(text)
    action_type = _infer_action_type(text)

    if action_type:
        intent = "action_request"
    elif any(token in lowered for token in ("history", "previous", "earlier", "before", "decided", "past")):
        intent = "history_query"
    elif any(token in lowered for token in ("conflict", "contradiction", "inconsistent", "disagree")):
        intent = "conflict_check"
    elif any(token in lowered for token in ("briefing", "brief", "summary", "recap", "overview")):
        intent = "briefing_request"
    # Person/entity lookups — no team keyword but mentions a name or ticket id → RAG
    elif not teams and re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b|NOVA-\d+', text):
        intent = "history_query"
    else:
        intent = "status_query"

    payload_json = None
    if action_type:
        payload_json = json.dumps(_infer_action_payload(text, action_type))

    _LOGGER.info(
        f"Classification (fallback/no-Gemini) | intent={intent} | "
        f"teams={teams} | action_type={action_type} | confidence=0.45"
    )
    return IntentClassification(
        intent=intent,
        teams=teams,
        topic=text[:140],
        time_window=time_window,
        action_type=action_type,
        action_payload_json=payload_json,
        confidence=0.45,
    )


async def _classify(text: str) -> IntentClassification:
    if not _GEMINI_KEY:
        return _fallback_classification(text)

    try:
        from google.genai import types as gt

        client = _get_gemini_client()
        resp = await client.aio.models.generate_content(
            model=_GEMINI_MODEL,
            contents=f"User request:\n{text}",
            config=gt.GenerateContentConfig(
                system_instruction=_CLASSIFIER_PROMPT,
                response_mime_type="application/json",
            ),
        )
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


def _briefing_roles(classification: IntentClassification) -> list[str] | None:
    return classification.teams or None


def _format_status_response(msg: FullBriefResponse, intent: str) -> str:
    lines = [
        f"Status mode: {msg.mode}",
        f"Overall confidence: {msg.overall_confidence:.2f}",
    ]

    if msg.role_statuses:
        lines.append("")
        lines.append("Role summaries:")
        for role_status in msg.role_statuses:
            blockers = "; ".join(role_status.blockers) if role_status.blockers else "none"
            lines.append(f"- {role_status.role}: {role_status.summary}")
            lines.append(f"  Blockers: {blockers}")

    if intent == "conflict_check":
        lines.append("")
        lines.append("Contradictions:")
        contradictions = msg.contradictions or ["No explicit contradictions found."]
        for entry in contradictions:
            lines.append(f"- {entry}")
    elif intent == "briefing_request":
        lines.append("")
        lines.append(f"Recommended action: {msg.recommended_action}")
        if msg.evidence_passports:
            lines.append("Evidence passports:")
            for passport in msg.evidence_passports[:3]:
                lines.append(f"- {passport.claim} [{passport.confidence}]")
    else:
        if msg.contradictions:
            lines.append("")
            lines.append("Detected contradictions:")
            for entry in msg.contradictions[:3]:
                lines.append(f"- {entry}")
        lines.append("")
        lines.append(f"Recommended action: {msg.recommended_action}")

    return "\n".join(lines)


def _format_history_response(msg: RAGResponse) -> str:
    sources = ", ".join(msg.source_ids) if msg.source_ids else "none"
    return (
        f"{msg.answer}\n\n"
        f"Sources: {sources}\n"
        f"Confidence: {msg.confidence:.2f} via {msg.retrieval_method}"
    )


def _format_action_response(msg: ActionResponse) -> str:
    if msg.success:
        text = msg.result or f"Action {msg.action_type} completed."
        if msg.stub:
            text += "\n\nNote: this was executed in stub mode."
        return text
    return msg.error or f"Action {msg.action_type} failed."


async def _send_chat_reply(ctx: Context, recipient: str, text: str) -> None:
    await ctx.send(
        recipient,
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid.uuid4(),
            content=[
                TextContent(type="text", text=text),
                EndSessionContent(type="end-session"),
            ],
        ),
    )


@chat_protocol.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(UTC),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    user_text = _extract_text(msg)
    if not user_text:
        await _send_chat_reply(ctx, sender, "I did not receive any text to route.")
        return

    ctx.logger.info(f"Incoming | sender={sender[:24]}… | text='{user_text[:120]}'")

    classification = await _classify(user_text)
    request_id = str(uuid.uuid4())

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
        roles = _briefing_roles(classification)
        ctx.logger.info(
            f"→ StatusAgent | id={request_id} | roles={roles} | "
            f"session_id={session_id} | dest={STATUS_AGENT_ADDRESS[:24]}…"
        )
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
        ctx.logger.info(
            f"→ HistoricalAgent | id={request_id} | role_filter={role_filter} | "
            f"dest={HISTORICAL_AGENT_ADDRESS[:24]}…"
        )
        await ctx.send(
            HISTORICAL_AGENT_ADDRESS,
            RAGRequest(
                request_id=request_id,
                question=user_text,
                role_filter=role_filter,
                top_k=5,
            ),
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

        payload_json = classification.action_payload_json or json.dumps(
            _infer_action_payload(user_text, action_type)
        )
        ctx.logger.info(
            f"→ PerformAction | id={request_id} | action_type={action_type} | "
            f"dest={PERFORM_ACTION_ADDRESS[:24]}…"
        )
        await ctx.send(
            PERFORM_ACTION_ADDRESS,
            ActionRequest(
                request_id=request_id,
                action_type=action_type,
                payload=payload_json,
                context=user_text,
                priority="normal",
            ),
        )
        return

    pending_requests.pop(request_id, None)
    ctx.logger.warning(f"Unclassified request | id={request_id} | intent={classification.intent}")
    await _send_chat_reply(ctx, sender, "I could not classify that request.")


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_chat_ack(_: Context, __: str, ___: ChatAcknowledgement):
    return


@orchestrator.on_message(FullBriefResponse)
async def handle_status_response(ctx: Context, sender: str, msg: FullBriefResponse):
    ctx.logger.info(
        f"← FullBriefResponse | id={msg.request_id} | mode={msg.mode} | "
        f"escalation={msg.escalation_required} | confidence={msg.overall_confidence:.2f} | "
        f"contradictions={len(msg.contradictions)} | passports={len(msg.evidence_passports)} | "
        f"deltas={len(msg.delta_claims or [])}"
    )
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        ctx.logger.warning(
            f"FullBriefResponse id={msg.request_id} has no matching pending request — dropped"
        )
        return

    status_sessions[pending["sender"]] = msg.session_id or status_sessions.get(pending["sender"], "")
    text = _format_status_response(msg, pending["intent"])
    ctx.logger.info(f"→ User | id={msg.request_id} | reply_len={len(text)} chars")
    await _send_chat_reply(ctx, pending["sender"], text)


@orchestrator.on_message(RAGResponse)
async def handle_history_response(ctx: Context, sender: str, msg: RAGResponse):
    ctx.logger.info(
        f"← RAGResponse | id={msg.request_id} | method={msg.retrieval_method} | "
        f"confidence={msg.confidence:.2f} | sources={msg.source_ids}"
    )
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        ctx.logger.warning(
            f"RAGResponse id={msg.request_id} has no matching pending request — dropped"
        )
        return

    ctx.logger.info(f"→ User | id={msg.request_id} | reply_len={len(msg.answer)} chars")
    await _send_chat_reply(ctx, pending["sender"], _format_history_response(msg))


@orchestrator.on_message(ActionResponse)
async def handle_action_response(ctx: Context, sender: str, msg: ActionResponse):
    ctx.logger.info(
        f"← ActionResponse | id={msg.request_id} | type={msg.action_type} | "
        f"success={msg.success} | stub={msg.stub} | action_id={msg.action_id}"
    )
    pending = pending_requests.pop(msg.request_id, None)
    if not pending:
        ctx.logger.warning(
            f"ActionResponse id={msg.request_id} has no matching pending request — dropped"
        )
        return

    ctx.logger.info(f"→ User | id={msg.request_id} | result='{(msg.result or msg.error or '')[:80]}'")
    await _send_chat_reply(ctx, pending["sender"], _format_action_response(msg))


orchestrator.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    if _ENDPOINT:
        print(f"Orchestrator endpoint: {_ENDPOINT}")
    if _AGENTVERSE:
        print(f"Agentverse URL: {_AGENTVERSE}")
    orchestrator.run()
