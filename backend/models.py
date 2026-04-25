"""
Shared uAgents message models for StandIn.
All agents import from here — do not use pydantic.BaseModel directly.
"""
from typing import List, Optional

from uagents import Model


# ---------------------------------------------------------------------------
# Core: Delegate <-> Orchestrator
# ---------------------------------------------------------------------------

class Claim(Model):
    claim: str
    source_ids: List[str]
    owner: str
    timestamp: str              # when claim was extracted (ISO-8601)
    source_timestamp: Optional[str] = None  # when the source doc was created/updated
    confidence: float           # 0.0 – 1.0
    risk: str                   # "high" | "medium" | "low"


class MeetingRequest(Model):
    request_id: str
    user_email: str
    topic: Optional[str] = None
    context: Optional[str] = None


class MeetingResponse(Model):
    request_id: str
    user_email: str
    role: str
    status: Optional[str] = "unknown"  # "ready" | "blocked" | "in_review" | "unknown"
    summary: str
    blockers: List[str]
    claims: List[Claim]
    confidence: float
    mode: Optional[str] = "live"       # "live" | "seeded"


# ---------------------------------------------------------------------------
# Core: Verifier <-> Orchestrator
# ---------------------------------------------------------------------------

class EvidencePassport(Model):
    claim: str
    source: str
    owner: str
    timestamp: str
    confidence: str             # "high" | "medium" | "low"
    contradictions: List[str]
    recommended_action: str
    escalation_required: bool


class VerifyRequest(Model):
    request_id: str
    responses: List[MeetingResponse]


class VerifyResponse(Model):
    request_id: str
    contradictions: List[str]
    stale_claims: List[str]
    unsupported_claims: List[str]
    missing_owners: List[str]
    escalation_required: bool
    escalation_reason: str
    evidence_passports: List[EvidencePassport]
    recommended_action: str


# ---------------------------------------------------------------------------
# Info Collector <-> Delegates / Orchestrator
# ---------------------------------------------------------------------------

class InfoResult(Model):
    content: str
    source_id: str
    source_type: str            # "slack" | "jira" | "drive" | "notion" | "web"
    relevance: float            # 0.0 – 1.0
    timestamp: str


class InfoRequest(Model):
    request_id: str
    query: str
    role_filter: Optional[str] = None   # limit results to a team's data
    sources: Optional[List[str]] = None  # specific tool names; None = all
    limit: Optional[int] = 10


class InfoResponse(Model):
    request_id: str
    query: str
    results: List[InfoResult]
    tools_attempted: List[str]
    tools_connected: List[str]  # empty until MCP tools are wired
    total_results: int


# ---------------------------------------------------------------------------
# Perform Action <-> Orchestrator / Escalation
# ---------------------------------------------------------------------------

class ActionRequest(Model):
    request_id: str
    action_type: str    # "send_email" | "send_slack" | "create_jira"
                        # | "schedule_meeting" | "create_action_item"
    payload: str        # JSON-serialised dict — caller must json.dumps()
    context: Optional[str] = None
    priority: Optional[str] = "normal"  # "normal" | "urgent"


class ActionResponse(Model):
    request_id: str
    action_type: str
    success: bool
    action_id: str
    result: Optional[str] = None
    error: Optional[str] = None
    stub: bool = True   # flips to False once real MCP tools are connected


# ---------------------------------------------------------------------------
# Research Agent <-> Orchestrator  (replaces 4 delegates + verifier in one hop)
# ---------------------------------------------------------------------------

class FullBriefRequest(Model):
    request_id: str
    user_email: str
    topic: Optional[str] = None
    roles: Optional[List[str]] = None   # None = all four roles
    context: Optional[str] = None
    session_id: Optional[str] = None   # set to resume a prior conversation


# ---------------------------------------------------------------------------
# RAG Agent <-> Orchestrator / any caller
# ---------------------------------------------------------------------------

class RAGRequest(Model):
    request_id: str
    question: str
    role_filter: Optional[str] = None   # "Engineering" | "Design" | etc.
    top_k: Optional[int] = 5


class RAGResponse(Model):
    request_id: str
    question: str
    answer: str
    source_ids: List[str]
    confidence: float
    retrieval_method: str   # "vector_search" | "keyword" | "no_results"


class FullBriefResponse(Model):
    request_id: str
    user_email: str
    role_statuses: List[MeetingResponse]        # one per role queried
    contradictions: List[str]
    stale_claims: List[str]
    unsupported_claims: List[str]
    evidence_passports: List[EvidencePassport]
    escalation_required: bool
    escalation_reason: str
    recommended_action: str
    overall_confidence: float
    mode: Optional[str] = "live"            # "live" | "seeded" | "partial"
    session_id: Optional[str] = None
    delta_claims: Optional[List[str]] = None  # what changed since last brief


# ---------------------------------------------------------------------------
# Perform Action — approval gate models
# ---------------------------------------------------------------------------

class PendingAction(Model):
    action_id: str
    action_type: str
    payload_json: str   # JSON string of the original payload
    priority: str
    created_at: str
    requested_by: Optional[str] = None


class PendingActionsResponse(Model):
    count: int
    actions: List[PendingAction]


class ApproveRequest(Model):
    action_id: str
    approver: Optional[str] = None


class ApproveResponse(Model):
    action_id: str
    action_type: str
    approved: bool
    result: Optional[str] = None
    error: Optional[str] = None


class RejectRequest(Model):
    action_id: str
    reason: Optional[str] = None


class RejectResponse(Model):
    action_id: str
    rejected: bool


# ---------------------------------------------------------------------------
# Watchdog <-> Status Agent  (reuses FullBriefRequest/Response)
# ---------------------------------------------------------------------------

class WatchdogAlert(Model):
    alert_id: str
    changes: List[str]          # human-readable change descriptions
    escalation_required: bool
    recommended_action: str
    previous_snapshot_at: Optional[str] = None
    current_snapshot_at: str


# ---------------------------------------------------------------------------
# Dashboard Graph API  (served via GET /graph on perform_action)
# ---------------------------------------------------------------------------

class GraphNode(Model):
    id: str
    name: str
    role: str
    team: str
    email: str
    agent_slug: Optional[str] = None


class GraphEdge(Model):
    from_user: str
    to_user: str
    type: str           # "meeting" | "slack_thread" | "jira"
    source_id: str
    label: str
    timestamp: str
    weight: int = 1     # incremented when the same pair interacts multiple times


class GraphResponse(Model):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    generated_at: str
    source: str         # "mongodb" | "hardcoded"
