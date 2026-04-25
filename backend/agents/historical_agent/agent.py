"""
Historical Agent — StandIn  (port 8009)

Answers historical questions about meetings, decisions, and org documents.
Runs in parallel with status_agent — status_agent answers "what is the
current status?", this agent answers "what was decided / what happened before?".

Retrieval pipeline (three tiers, automatic fallback):
  Tier 1 — MongoDB Atlas Vector Search  (when MONGODB_URI + vector index ready)
  Tier 2 — Keyword search over all 25 seed documents  (always available, no setup)
  Tier 3 — Gemini synthesis with no retrieved context  (last resort)

To activate Tier 1:
  1. Run:  python data/seed_db.py   (seeds docs + embeddings into MongoDB)
  2. Create the vector index in Atlas UI (seed_db.py prints instructions).

Run: python agents/historical_agent/agent.py
"""

import glob
import json
import math
import os
import sys
from datetime import datetime, UTC
from typing import Optional

from dotenv import load_dotenv
from uagents import Agent, Context, Model

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

from data.company_data import CALENDAR, JIRA, SLACK, USERS
from models import RAGRequest, RAGResponse

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
_SEED = os.getenv("HISTORICAL_AGENT_SEED", "historical_agent_standin_seed_v1")
_PORT = int(os.getenv("HISTORICAL_AGENT_PORT", "8009"))
_GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
_MONGODB_URI  = os.getenv("MONGODB_URI", "")
_VECTOR_INDEX = os.getenv("VECTOR_INDEX_NAME", "standin_vector_index")
_EMBED_MODEL  = "text-embedding-004"   # 768-dim, free tier, fast

agent = Agent(
    name="historical_agent",
    seed=_SEED,
    port=_PORT,
    mailbox=True,
    publish_agent_details=True,
)

_SYSTEM = (
    "You are StandIn, an AI coordination assistant. Answer the user's question "
    "using ONLY the provided context documents. Be concise and factual. "
    "If the context does not contain a clear answer, say so explicitly — "
    "never invent information that is not present in the context."
)

# In-memory cache of seed docs for Tier 2 keyword search (loaded at startup)
_SEED_DOCS: list[dict] = []


# ---------------------------------------------------------------------------
# Tier 1 — MongoDB Atlas Vector Search
# ---------------------------------------------------------------------------

def _get_db():
    if not _MONGODB_URI:
        raise RuntimeError("MONGODB_URI not set")
    from pymongo import MongoClient
    client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=4000)
    return client["standin"]


async def _embed(text: str) -> list[float]:
    """Embed a single text string using Gemini text-embedding-004."""
    from google import genai
    client = genai.Client(api_key=_GEMINI_KEY)
    result = await client.aio.models.embed_content(
        model=_EMBED_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


async def _vector_search(
    question: str, role_filter: Optional[str], top_k: int
) -> list[dict]:
    """
    Atlas Vector Search — returns top-k documents by cosine similarity.
    Requires seed_db.py to have been run and the vector index to exist.
    """
    query_vec = await _embed(question)

    pipeline: list[dict] = [
        {
            "$vectorSearch": {
                "index":        _VECTOR_INDEX,
                "path":         "embedding",
                "queryVector":  query_vec,
                "numCandidates": top_k * 5,
                "limit":        top_k,
                **({"filter": {"role": role_filter}} if role_filter else {}),
            }
        },
        {
            "$project": {
                "embedding": 0,
                "_id":       0,
                "score":     {"$meta": "vectorSearchScore"},
            }
        },
    ]

    db = _get_db()
    docs = list(db["documents"].aggregate(pipeline))
    return docs


# ---------------------------------------------------------------------------
# Tier 2 — Keyword search over seed JSON files (always available)
# ---------------------------------------------------------------------------

def _cosine(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _keyword_search(
    question: str, role_filter: Optional[str], top_k: int
) -> list[dict]:
    """
    Simple BM25-style keyword overlap over the cached seed JSON files.
    No API calls needed — works with zero setup.
    """
    query_tokens = set(question.lower().split())
    scored: list[tuple[float, dict]] = []

    for doc in _SEED_DOCS:
        if role_filter and doc.get("role", "").lower() != role_filter.lower():
            continue

        haystack = (
            doc.get("title", "")   + " " +
            doc.get("content", "") + " " +
            " ".join(doc.get("tags", []))
        ).lower()

        # Token overlap score, boosted for title hits
        title_tokens = set(doc.get("title", "").lower().split())
        body_hits  = sum(1 for t in query_tokens if t in haystack)
        title_hits = sum(2 for t in query_tokens if t in title_tokens)
        score = body_hits + title_hits

        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return [doc for _, doc in scored[:top_k]]


# ---------------------------------------------------------------------------
# Gemini synthesis
# ---------------------------------------------------------------------------

async def _synthesize(
    question: str,
    docs: list[dict],
    retrieval_method: str,
) -> tuple[str, float]:
    """
    Synthesise an answer from retrieved documents.
    Returns (answer_text, confidence).
    """
    if not _GEMINI_KEY:
        if not docs:
            return "No relevant documents found and Gemini is not configured.", 0.1
        # Plain-text summary without LLM
        snippets = [
            f"[{d.get('id', '?')}] {d.get('title', '')}: "
            f"{d.get('content', '')[:200]}"
            for d in docs
        ]
        return "Based on seed documents:\n\n" + "\n\n".join(snippets), 0.5

    context_blocks = []
    for d in docs:
        block = (
            f"Document: {d.get('id', '?')}\n"
            f"Title: {d.get('title', '')}\n"
            f"Role: {d.get('role', 'N/A')}\n"
            f"Date: {d.get('timestamp', 'unknown')}\n"
            f"Content:\n{d.get('content', '')[:600]}"
        )
        context_blocks.append(block)

    if not context_blocks:
        context_str = "(No relevant documents found in the knowledge base.)"
    else:
        context_str = "\n\n---\n\n".join(context_blocks)

    prompt = (
        f"Question: {question}\n\n"
        f"Context documents ({retrieval_method}):\n\n"
        f"{context_str}\n\n"
        "Answer the question using only the context above. "
        "Cite document IDs where relevant. "
        "If the context does not contain the answer, say so clearly."
    )

    from google import genai
    from google.genai import types as gt

    client = genai.Client(api_key=_GEMINI_KEY)
    resp = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=gt.GenerateContentConfig(system_instruction=_SYSTEM),
    )

    # Confidence heuristic: more sources + vector search = higher confidence
    base = 0.85 if retrieval_method == "vector_search" else 0.65
    confidence = min(0.95, base + 0.02 * len(docs))

    return resp.text.strip(), confidence


# ---------------------------------------------------------------------------
# Startup — load seed docs for Tier 2
# ---------------------------------------------------------------------------

def _build_seed_cache() -> list[dict]:
    """Load all 25 documents — seed JSON files + Slack + Jira + Calendar."""
    docs: list[dict] = []

    # 12 seed JSON files
    seed_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "seed")
    )
    for path in glob.glob(os.path.join(seed_dir, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                docs.append(json.load(f))
        except Exception:
            pass

    # Slack messages
    for msg in SLACK.values():
        thread_text = "\n".join(
            f"{t['sender']}: {t['content']}" for t in msg.get("thread", [])
        )
        content = msg["content"] + ("\n\nThread:\n" + thread_text if thread_text else "")
        docs.append({
            "id":      msg["id"],
            "title":   f"Slack #{msg['channel']} — {msg['sender_name']}",
            "type":    "slack_message",
            "role":    msg.get("role", ""),
            "tags":    ["slack", msg["channel"].lstrip("#")],
            "content": content,
        })

    # Jira tickets — role derived from assignee's team, fallback to label scan
    _label_role_map = {"design": "Design", "gtm": "GTM", "marketing": "GTM",
                       "legal": "GTM", "engineering": "Engineering", "backend": "Engineering",
                       "api": "Engineering", "qa": "Engineering"}
    for ticket in JIRA.values():
        assignee = ticket.get("assignee", "")
        role = USERS.get(assignee, {}).get("team", "")
        if not role:
            for label in ticket.get("labels", []):
                role = _label_role_map.get(label.lower(), "")
                if role:
                    break
        docs.append({
            "id":      ticket["id"],
            "title":   f"[{ticket['id']}] {ticket['title']}",
            "type":    "jira_ticket",
            "role":    role,
            "tags":    ticket.get("labels", []) + ["jira"],
            "content": (
                f"Title: {ticket['title']}\n"
                f"Status: {ticket['status']}\n"
                f"Priority: {ticket['priority']}\n"
                f"Assignee: {ticket.get('assignee', 'unassigned')}\n"
                f"Description: {ticket.get('description', '')}\n"
                f"Labels: {', '.join(ticket.get('labels', []))}"
            ),
        })

    # Calendar events
    for meeting in CALENDAR.values():
        docs.append({
            "id":      meeting["id"],
            "title":   meeting["title"],
            "type":    "calendar_event",
            "role":    "",
            "tags":    ["calendar", "meeting"],
            "content": (
                f"Title: {meeting['title']}\n"
                f"Date: {meeting['date']} {meeting['time']}\n"
                f"Attendees: {', '.join(meeting.get('attendees', []))}\n"
                f"Agenda: {'; '.join(meeting.get('agenda', []))}\n"
                f"Description: {meeting.get('description', '')}"
            ),
        })

    return docs


@agent.on_startup()
async def on_startup(ctx: Context):
    global _SEED_DOCS
    _SEED_DOCS = _build_seed_cache()

    tier1 = "ready" if (_MONGODB_URI and _GEMINI_KEY) else "not configured"
    ctx.logger.info(
        f"Historical Agent online | address={ctx.agent.address} | port={_PORT}"
    )
    ctx.logger.info(
        f"Tier 1 (vector search): {tier1} | "
        f"Tier 2 (keyword): {len(_SEED_DOCS)} docs loaded | "
        f"Gemini: {'configured' if _GEMINI_KEY else 'not configured'}"
    )
    if not _MONGODB_URI or not _GEMINI_KEY:
        missing = [k for k, v in [("MONGODB_URI", _MONGODB_URI), ("GEMINI_API_KEY", _GEMINI_KEY)] if not v]
        ctx.logger.warning(
            f"{', '.join(missing)} not set — Tier 1 vector search DISABLED. "
            "Falling back to keyword search only."
        )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

@agent.on_message(RAGRequest)
async def handle_rag(ctx: Context, sender: str, msg: RAGRequest):
    # NOTE: this agent receives typed uAgents messages, NOT Chat Protocol.
    # Orchestrator must call: await ctx.send(HISTORICAL_AGENT_ADDRESS, RAGRequest(...))
    ctx.logger.info(
        f"RAGRequest | id={msg.request_id} | "
        f"question='{msg.question[:60]}' | "
        f"role_filter={msg.role_filter} | top_k={msg.top_k or 5}"
    )
    try:
        await _handle_rag_inner(ctx, sender, msg)
    except Exception as exc:
        ctx.logger.error(f"handle_rag crashed: {exc}", exc_info=True)
        await ctx.send(sender, RAGResponse(
            request_id=msg.request_id,
            question=msg.question,
            answer="Internal error — RAG handler crashed. Check agent logs.",
            source_ids=[],
            confidence=0.0,
            retrieval_method="no_results",
        ))


async def _handle_rag_inner(ctx: Context, sender: str, msg: RAGRequest):
    top_k = msg.top_k or 5
    docs: list[dict] = []
    retrieval_method = "no_results"

    # ── Tier 1: Vector Search ─────────────────────────────────────────────
    if _MONGODB_URI and _GEMINI_KEY:
        try:
            docs = await _vector_search(msg.question, msg.role_filter, top_k)
            if docs:
                retrieval_method = "vector_search"
                ctx.logger.info(f"Vector search returned {len(docs)} docs")
        except Exception as exc:
            ctx.logger.warning(
                f"Vector search failed (index may not exist yet): {exc}. "
                f"Falling back to keyword search."
            )

    # ── Tier 2: Keyword Search ────────────────────────────────────────────
    if not docs:
        docs = _keyword_search(msg.question, msg.role_filter, top_k)
        if docs:
            retrieval_method = "keyword"
            ctx.logger.info(f"Keyword search returned {len(docs)} docs")
        else:
            ctx.logger.info("No documents matched — synthesising with no context")

    # ── Synthesis ─────────────────────────────────────────────────────────
    answer, confidence = await _synthesize(msg.question, docs, retrieval_method)
    source_ids = [d.get("id", "?") for d in docs]

    response = RAGResponse(
        request_id=msg.request_id,
        question=msg.question,
        answer=answer,
        source_ids=source_ids,
        confidence=confidence,
        retrieval_method=retrieval_method,
    )

    ctx.logger.info(
        f"RAGResponse | method={retrieval_method} | "
        f"sources={source_ids} | confidence={confidence:.2f}"
    )
    await ctx.send(sender, response)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class _HealthResponse(Model):
    status: str
    agent: str
    tier1: str
    docs_loaded: int
    gemini: str
    timestamp: str


@agent.on_rest_get("/health", _HealthResponse)
async def health(ctx: Context) -> _HealthResponse:
    return _HealthResponse(
        status="ok",
        agent="historical_agent",
        tier1="ready" if (_MONGODB_URI and _GEMINI_KEY) else "not configured",
        docs_loaded=len(_SEED_DOCS),
        gemini="configured" if _GEMINI_KEY else "not configured",
        timestamp=datetime.now(UTC).isoformat(),
    )


if __name__ == "__main__":
    agent.run()
