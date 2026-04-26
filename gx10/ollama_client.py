"""Thin Ollama HTTP wrapper with strict timeout + JSON-validated fallback."""
import json
import os
from typing import Optional

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "12"))


def _extract_json_blob(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def generate_json(prompt: str, system: Optional[str] = None) -> Optional[dict]:
    """Call Ollama and return a parsed JSON dict, or None on any failure."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    response_text = data.get("response", "") if isinstance(data, dict) else ""
    return _extract_json_blob(response_text)


def is_available() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{OLLAMA_URL}/api/tags")
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
