"""
Quick RAG test — run from project root:
    venv/Scripts/python.exe backend/test_rag.py

Tests all three retrieval tiers against your seeded MongoDB data.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "")
GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")

EMBED_MODEL   = "models/gemini-embedding-001"
VECTOR_INDEX  = "standin_vector_index"
DB_NAME       = "standin"
COLLECTION    = "documents"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float] | None:
    if not GEMINI_KEY:
        return None
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_KEY)
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return result.embeddings[0].values


def _keyword_search(query: str, top_k: int = 5) -> list[dict]:
    from pymongo import MongoClient
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    tokens = query.lower().split()
    results = []
    for doc in db[COLLECTION].find({}, {"_id": 0, "embedding": 0}):
        text = (doc.get("title", "") + " " + doc.get("content", "")).lower()
        score = sum(2 if t in doc.get("title", "").lower() else 1 for t in tokens if t in text)
        if score > 0:
            results.append((score, doc))
    results.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in results[:top_k]]


def _vector_search(query: str, top_k: int = 5) -> list[dict]:
    vec = _embed(query)
    if not vec:
        return []
    from pymongo import MongoClient
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    pipeline = [
        {"$vectorSearch": {
            "index": VECTOR_INDEX,
            "path": "embedding",
            "queryVector": vec,
            "numCandidates": top_k * 10,
            "limit": top_k,
        }},
        {"$project": {"_id": 0, "embedding": 0, "score": {"$meta": "vectorSearchScore"}}},
    ]
    return list(db[COLLECTION].aggregate(pipeline))


async def _gemini_answer(question: str, docs: list[dict]) -> str:
    if not GEMINI_KEY:
        return "(Gemini not configured)"
    from google import genai
    client = genai.Client(api_key=GEMINI_KEY)
    context = "\n\n".join(
        f"[{d.get('id','?')}] {d.get('title','')}\n{d.get('content','')[:400]}"
        for d in docs
    )
    prompt = (
        f"Answer this question using only the documents below. "
        f"Be concise (2-3 sentences max).\n\n"
        f"Question: {question}\n\n"
        f"Documents:\n{context}"
    )
    resp = await client.aio.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return resp.text.strip()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_keyword(query: str):
    print(f"\n{'-'*60}")
    print(f"TIER 2 — Keyword search: '{query}'")
    docs = _keyword_search(query)
    if not docs:
        print("  No results")
        return
    for d in docs:
        print(f"  [{d.get('role','?'):12}] {d.get('id','?'):30} — {d.get('title','')[:50]}")


def test_vector(query: str):
    print(f"\n{'-'*60}")
    print(f"TIER 1 — Vector search: '{query}'")
    if not (MONGODB_URI and GEMINI_KEY):
        print("  Skipped — MONGODB_URI or GEMINI_API_KEY not set")
        return
    try:
        docs = _vector_search(query)
        if not docs:
            print("  No results — index may still be building (wait ~2 min after seeding)")
            return
        for d in docs:
            score = d.pop("score", None)
            score_str = f"  score={score:.3f}" if score else ""
            print(f"  [{d.get('role','?'):12}] {d.get('id','?'):30}{score_str} — {d.get('title','')[:40]}")
    except Exception as e:
        if "index" in str(e).lower() or "not found" in str(e).lower():
            print(f"  Vector index not ready yet — wait ~2 min and retry")
        else:
            print(f"  Error: {e}")


async def test_full_rag(query: str):
    print(f"\n{'-'*60}")
    print(f"FULL RAG (vector -> keyword -> Gemini): '{query}'")
    docs = _vector_search(query) or _keyword_search(query)
    method = "vector" if docs and GEMINI_KEY else "keyword"
    print(f"  Retrieved {len(docs)} docs via {method} search")
    answer = await _gemini_answer(query, docs)
    print(f"  Answer: {answer}")


async def main():
    print("StandIn RAG Test")
    print(f"MongoDB: {'connected' if MONGODB_URI else 'NOT SET'}")
    print(f"Gemini:  {'configured' if GEMINI_KEY else 'NOT SET'}")

    # Count docs
    if MONGODB_URI:
        from pymongo import MongoClient
        db = MongoClient(MONGODB_URI)[DB_NAME]
        total = db[COLLECTION].count_documents({})
        with_emb = db[COLLECTION].count_documents({"embedding": {"$exists": True}})
        print(f"Corpus:  {total} docs ({with_emb} with embeddings)\n")

    queries = [
        "What is the status of the checkout API?",
        "Is the launch blocked?",
        "What did engineering report about NOVA-142?",
        "What are the GTM plans for launch?",
    ]

    # Keyword test (always works)
    for q in queries[:2]:
        test_keyword(q)

    # Vector test (works after index builds)
    for q in queries[:2]:
        test_vector(q)

    # Full RAG with Gemini answer
    for q in queries:
        await test_full_rag(q)

    print(f"\n{'-'*60}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
