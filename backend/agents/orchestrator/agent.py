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
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_LOGGER = logging.getLogger("standin_orchestrator")

_GEMINI_CLIENT = None


def _get_gemini_client():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None and _GEMINI_KEY:
        from google import genai
        _GEMINI_CLIENT = genai.Client(api_key=_GEMINI_KEY)
    return _GEMINI_CLIENT


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

STATUS_AGENT_ADDRESS = os.getenv("STATUS_AGENT_ADDRESS")
HISTORICAL_AGENT_ADDRESS = os.getenv("HISTORICAL_AGENT_ADDRESS")
PERFORM_ACTION_ADDRESS = os.getenv("PERFORM_ACTION_ADDRESS")

chat_proto = Protocol(spec=chat_protocol_spec)
pending_requests: dict[str, dict] = {}
status_sessions: dict[str, str] = {}
# Tracks in-flight fanout pairs: merge_id → {sender, history, status}
fanout_state: dict[str, dict] = {}
# Tracks when each request was sent for RTT logging
_request_sent_at: dict[str, float] = {}

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

_CLASSIFIER_PROMPT = """
You classify user requests for a coordination orchestrator called StandIn.

## Company context
Company: NovaLoop. Active project: "Checkout AI Assistant — Launch Alpha". Deadline: Monday 2026-04-28.
Teams: Engineering, Design, GTM, Product.
Known tickets: NOVA-139 (GTM launch email review, in progress), NOVA-140 (design asset sign-off, done),
  NOVA-141 (GTM launch email review, blocked), NOVA-142 (checkout API /v1→/v2 migration, critical blocker),
  NOVA-143 (QA smoke test sign-off, blocked).
Known people: Alice Chen (Product Manager), Derek Vasquez (Lead Engineer, Engineering),
  Priya Mehta (Design Lead), Sam Okafor (GTM Manager), Kai Torres (QA, Engineering),
  Mira Lopez (Frontend, Engineering), Jules Park (Backend, Engineering).
Known conflict: Design says launch page is ready; Engineering says NOVA-142 blocks checkout API.

## Sub-agents available
- status_agent   : live status, blockers, conflict detection across teams (uses Slack + Jira + RAG)
- historical_agent: past decisions, meeting notes, previous discussions (uses MongoDB vector/keyword search)
- perform_action : send Slack, email, create Jira tickets, schedule meetings, create action items

## Return strict JSON with this schema
{
  "intent": "status_query|conflict_check|action_request|history_query|briefing_request",
  "teams": ["Engineering" | "Design" | "GTM" | "Product"],
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
- Any NOVA-XXX ticket lookup → history_query (the RAG corpus has all ticket history)
- Any person name lookup → history_query
- Calendar read requests (upcoming/current meetings) → status_query
- Past calendar/meeting history → history_query
- Calendar create/update requests → action_request (schedule_meeting)
- Extract teams only from explicit team mentions.
- Keep topic short and literal — include ticket ID if present (e.g. "NOVA-141 GTM launch email").
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
        payload["text"] = text
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
                thinking_config=gt.ThinkingConfig(thinking_budget=0),
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


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(UTC), acknowledged_msg_id=msg.msg_id))
    user_text = _extract_text(msg)
    if not user_text:
        await _send_chat_reply(ctx, sender, "I did not receive any text to route.")
        return

    ctx.logger.info(f"Incoming | sender={sender[:24]}… | text='{user_text[:200]}'")
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
            roles = _briefing_roles(classification)
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

            payload_json = classification.action_payload_json or json.dumps(
                _infer_action_payload(user_text, action_type)
            )
            ctx.logger.info(
                f"→ PerformAction | id={request_id} | action_type={action_type} | "
                f"dest={PERFORM_ACTION_ADDRESS[:24]}… | payload_keys={list(json.loads(payload_json).keys())}"
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
    await _send_chat_reply(ctx, pending["sender"], _format_action_response(msg))


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


if __name__ == "__main__":
    if _ENDPOINT:
        print(f"Orchestrator endpoint: {_ENDPOINT}")
    if _AGENTVERSE:
        print(f"Agentverse URL: {_AGENTVERSE}")
    orchestrator.run()
