"""
MongoDB Seeder — StandIn
Loads all 12 seed documents + company_data into MongoDB,
generates Gemini embeddings, and sets up the vector search index.

Run once (safe to re-run — uses upsert):
    python data/seed_db.py

Requires in .env:
    MONGODB_URI=mongodb+srv://...
    GEMINI_API_KEY=...   (optional — skips embeddings if missing)
"""

import json
import os
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from data.company_data import CALENDAR, JIRA, SLACK, USERS

_LABEL_ROLE_MAP = {"design": "Design", "gtm": "GTM", "marketing": "GTM",
                   "legal": "GTM", "engineering": "Engineering", "backend": "Engineering",
                   "api": "Engineering", "qa": "Engineering"}

_MONGODB_URI = os.getenv("MONGODB_URI", "")
_GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")
_EMBED_MODEL = "text-embedding-004"
_EMBED_DIM   = 768
_SEED_DIR    = Path(__file__).parent / "seed"


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _embed_sync(text: str) -> list[float] | None:
    """Return embedding vector or None if Gemini not configured."""
    if not _GEMINI_KEY:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=_GEMINI_KEY)
        result = client.models.embed_content(model=_EMBED_MODEL, contents=text)
        return result.embeddings[0].values
    except Exception as exc:
        print(f"    [warn] Embedding failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Document builders — convert each data source into a flat MongoDB doc
# ---------------------------------------------------------------------------

def _docs_from_seed_files() -> list[dict]:
    docs = []
    for path in sorted(_SEED_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        docs.append({
            "id":         raw["id"],
            "source":     "seed_file",
            "filename":   raw.get("filename", path.name),
            "title":      raw.get("title", ""),
            "type":       raw.get("type", "document"),
            "role":       raw.get("role", ""),
            "author":     raw.get("author", ""),
            "timestamp":  raw.get("timestamp", ""),
            "tags":       raw.get("tags", []),
            "content":    raw.get("content", ""),
            "sensitive_flags": raw.get("sensitive_flags", []),
        })
    return docs


def _docs_from_slack() -> list[dict]:
    docs = []
    for msg in SLACK.values():
        thread_text = "\n".join(
            f"{t['sender']}: {t['content']}" for t in msg.get("thread", [])
        )
        content = msg["content"] + ("\n\nThread:\n" + thread_text if thread_text else "")
        docs.append({
            "id":        msg["id"],
            "source":    "slack",
            "title":     f"Slack #{msg['channel']} — {msg['sender_name']}",
            "type":      "slack_message",
            "role":      msg.get("role", ""),
            "author":    msg.get("sender", ""),
            "timestamp": msg.get("timestamp", ""),
            "tags":      ["slack", msg["channel"].lstrip("#")],
            "content":   content,
            "sensitive_flags": [],
        })
    return docs


def _docs_from_jira() -> list[dict]:
    docs = []
    for ticket in JIRA.values():
        assignee = ticket.get("assignee", "")
        role = USERS.get(assignee, {}).get("team", "")
        if not role:
            for label in ticket.get("labels", []):
                role = _LABEL_ROLE_MAP.get(label.lower(), "")
                if role:
                    break
        content = (
            f"Title: {ticket['title']}\n"
            f"Status: {ticket['status']}\n"
            f"Priority: {ticket['priority']}\n"
            f"Assignee: {ticket.get('assignee', 'unassigned')}\n"
            f"Description: {ticket.get('description', '')}\n"
            f"Labels: {', '.join(ticket.get('labels', []))}"
        )
        docs.append({
            "id":        ticket["id"],
            "source":    "jira",
            "title":     f"[{ticket['id']}] {ticket['title']}",
            "type":      "jira_ticket",
            "role":      role,
            "author":    ticket.get("reporter", ""),
            "timestamp": ticket.get("updated", ticket.get("created", "")),
            "tags":      ticket.get("labels", []) + ["jira"],
            "content":   content,
            "sensitive_flags": [],
        })
    return docs


def _docs_from_calendar() -> list[dict]:
    docs = []
    for meeting in CALENDAR.values():
        content = (
            f"Title: {meeting['title']}\n"
            f"Date: {meeting['date']} {meeting['time']} {meeting.get('timezone', '')}\n"
            f"Duration: {meeting.get('duration_minutes', '?')} min\n"
            f"Attendees: {', '.join(meeting.get('attendees', []))}\n"
            f"Agenda:\n" +
            "\n".join(f"  - {a}" for a in meeting.get("agenda", [])) +
            f"\n\nDescription: {meeting.get('description', '')}"
        )
        docs.append({
            "id":        meeting["id"],
            "source":    "calendar",
            "title":     meeting["title"],
            "type":      "calendar_event",
            "role":      "",  # all teams
            "author":    meeting.get("organizer", ""),
            "timestamp": f"{meeting['date']}T{meeting['time']}:00Z",
            "tags":      ["calendar", "meeting"],
            "content":   content,
            "sensitive_flags": [],
        })
    return docs


# ---------------------------------------------------------------------------
# Interaction builder — graph edges for the dashboard
# ---------------------------------------------------------------------------

def _interactions_from_data() -> list[dict]:
    """
    Extract user-to-user interaction edges from Slack threads, Jira, and Calendar.
    Stored in standin.interactions — used by GET /graph endpoint.
    """
    interactions: list[dict] = []

    # Slack thread replies (sender → each thread responder)
    for msg in SLACK.values():
        for reply in msg.get("thread", []):
            if reply["sender"] != msg["sender"]:
                interactions.append({
                    "id":        f"{msg['id']}_{reply['sender']}",
                    "from_user": msg["sender"],
                    "to_user":   reply["sender"],
                    "type":      "slack_thread",
                    "source_id": msg["id"],
                    "label":     f"Thread in #{msg['channel']}",
                    "timestamp": reply.get("timestamp", msg["timestamp"]),
                })

    # Jira reporter → assignee (skip self-assignments)
    for ticket in JIRA.values():
        reporter = ticket.get("reporter", "")
        assignee = ticket.get("assignee", "")
        if reporter and assignee and reporter != assignee:
            interactions.append({
                "id":        f"{ticket['id']}_jira",
                "from_user": reporter,
                "to_user":   assignee,
                "type":      "jira",
                "source_id": ticket["id"],
                "label":     ticket["title"][:80],
                "timestamp": ticket.get("created", ""),
            })

    # Calendar co-attendees (every unique pair per meeting)
    for meeting in CALENDAR.values():
        attendees = meeting.get("attendees", [])
        ts = f"{meeting['date']}T{meeting['time']}:00Z"
        for i, a in enumerate(attendees):
            for b in attendees[i + 1:]:
                interactions.append({
                    "id":        f"{meeting['id']}_{a}_{b}",
                    "from_user": a,
                    "to_user":   b,
                    "type":      "meeting",
                    "source_id": meeting["id"],
                    "label":     meeting["title"],
                    "timestamp": ts,
                })

    return interactions


# ---------------------------------------------------------------------------
# MongoDB upsert
# ---------------------------------------------------------------------------

def _upsert_docs(db, collection: str, docs: list[dict], embed: bool) -> int:
    from pymongo import UpdateOne

    ops = []
    for i, doc in enumerate(docs):
        if embed:
            text_for_embedding = f"{doc['title']}\n{doc['content'][:1200]}"
            vec = _embed_sync(text_for_embedding)
            if vec:
                doc["embedding"] = vec
            # small delay to avoid rate limits
            if i > 0 and i % 5 == 0:
                time.sleep(0.5)

        doc["seeded_at"] = datetime.now(UTC).isoformat()
        ops.append(UpdateOne({"id": doc["id"]}, {"$set": doc}, upsert=True))

    if ops:
        result = db[collection].bulk_write(ops)
        return result.upserted_count + result.modified_count
    return 0


# ---------------------------------------------------------------------------
# Vector index setup
# ---------------------------------------------------------------------------

def _create_vector_index(db) -> bool:
    """
    Attempt to create the Atlas Vector Search index via PyMongo.
    Returns True if successful, False if not (Atlas tier or API limitation).
    """
    index_def = {
        "name": "standin_vector_index",
        "type": "vectorSearch",
        "definition": {
            "fields": [
                {
                    "type":          "vector",
                    "path":          "embedding",
                    "numDimensions": _EMBED_DIM,
                    "similarity":    "cosine",
                },
                {
                    "type": "filter",
                    "path": "role",
                },
                {
                    "type": "filter",
                    "path": "source",
                },
            ]
        },
    }
    try:
        db["documents"].create_search_index(index_def)
        return True
    except Exception as exc:
        print(f"    [info] Programmatic index creation not available: {exc}")
        return False


def _print_index_instructions() -> None:
    print("""
  ── Manual Atlas Vector Index Setup ─────────────────────────────────────
  1. Open MongoDB Atlas → your cluster → Search Indexes → Create Index
  2. Choose JSON editor, select collection: standin.documents
  3. Paste this definition:

  {
    "name": "standin_vector_index",
    "type": "vectorSearch",
    "definition": {
      "fields": [
        { "type": "vector", "path": "embedding",
          "numDimensions": 768, "similarity": "cosine" },
        { "type": "filter", "path": "role" },
        { "type": "filter", "path": "source" }
      ]
    }
  }

  4. Click Create — index builds in ~2 min on M0 free tier.
  5. RAG Agent Tier 1 (vector search) activates automatically.
  ─────────────────────────────────────────────────────────────────────────
""")


# ---------------------------------------------------------------------------
# Seeder entry point
# ---------------------------------------------------------------------------

def seed():
    if not _MONGODB_URI:
        print("ERROR: MONGODB_URI not set in .env — aborting.")
        sys.exit(1)

    from pymongo import MongoClient
    client = MongoClient(_MONGODB_URI, serverSelectionTimeoutMS=6000)
    db = client["standin"]

    embed = bool(_GEMINI_KEY)
    print(f"\nStandIn MongoDB Seeder")
    print(f"  MongoDB: connected")
    print(f"  Gemini:  {'configured — will generate embeddings' if embed else 'not set — skipping embeddings (Tier 2 only)'}")
    print(f"  Seed dir: {_SEED_DIR}\n")

    # ── Seed documents collection ─────────────────────────────────────────
    all_docs = (
        _docs_from_seed_files() +
        _docs_from_slack()      +
        _docs_from_jira()       +
        _docs_from_calendar()
    )
    print(f"  Seeding {len(all_docs)} documents into standin.documents ...")
    n = _upsert_docs(db, "documents", all_docs, embed=embed)
    print(f"    done — {n} upserted/modified, {len(all_docs) - n} unchanged")

    # ── Seed agent_profiles collection ───────────────────────────────────
    print("  Seeding agent_profiles ...")
    from pymongo import UpdateOne
    profile_ops = [
        UpdateOne(
            {"agent_id": uid},
            {"$set": {
                "agent_id":   uid,
                "name":       u["name"],
                "role":       u["role"],
                "email":      u["email"],
                "team":       u["team"],
                "agent_slug": u.get("agent", ""),
                "agentverse_address": u.get("agentverse_address", ""),
                "seeded_at":  datetime.now(UTC).isoformat(),
            }},
            upsert=True,
        )
        for uid, u in USERS.items()
    ]
    if profile_ops:
        db["agent_profiles"].bulk_write(profile_ops)
        print(f"    done — {len(profile_ops)} profiles")

    # ── Seed meetings collection from calendar ────────────────────────────
    print("  Seeding meetings ...")
    meeting_ops = [
        UpdateOne(
            {"meeting_id": mid},
            {"$set": {
                "meeting_id":  mid,
                **m,
                "seeded_at":   datetime.now(UTC).isoformat(),
            }},
            upsert=True,
        )
        for mid, m in CALENDAR.items()
    ]
    if meeting_ops:
        db["meetings"].bulk_write(meeting_ops)
        print(f"    done — {len(meeting_ops)} meetings")

    # ── Seed interactions collection (graph edges) ───────────────────────
    print("  Seeding interactions (graph edges) ...")
    ix_data = _interactions_from_data()
    ix_ops = [
        UpdateOne(
            {"id": ix["id"]},
            {"$set": {**ix, "seeded_at": datetime.now(UTC).isoformat()}},
            upsert=True,
        )
        for ix in ix_data
    ]
    if ix_ops:
        db["interactions"].bulk_write(ix_ops)
        print(f"    done — {len(ix_ops)} interaction edges")

    # ── Vector index ──────────────────────────────────────────────────────
    if embed:
        print("\n  Creating vector search index ...")
        if _create_vector_index(db):
            print("    done — index 'standin_vector_index' created (builds in ~2 min)")
        else:
            print("    could not create programmatically.")
            _print_index_instructions()
    else:
        print("\n  Skipping vector index (no embeddings — add GEMINI_API_KEY to .env)")
        print("  Tier 2 keyword search will work immediately.")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n  Collections seeded:")
    for col in ["documents", "agent_profiles", "meetings", "interactions"]:
        count = db[col].count_documents({})
        has_emb = db[col].count_documents({"embedding": {"$exists": True}}) if col == "documents" else 0
        emb_note = f"  ({has_emb} with embeddings)" if col == "documents" else ""
        print(f"    standin.{col}: {count} documents{emb_note}")

    print("\nDone. Run 'python backend/main.py' or 'python backend/agents/historical_agent/agent.py' to start the Historical agent.\n")


if __name__ == "__main__":
    seed()

