"""
HTTP client for the standin-gx10 edge trust layer.

The GX10 runs separately on the ASUS Ascent on the LAN. This module is a thin,
stdlib-only wrapper so the rest of the backend can call it without adding deps.
If the GX10 is unreachable, every helper degrades gracefully: redaction returns
the original documents unchanged, contradiction-check returns an empty verdict,
and the rest of the pipeline keeps running. The trustLayerStatus field tells
the orchestrator (and the dashboard) which path was taken.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

_LOGGER = logging.getLogger("gx10_client")

GX10_BASE_URL = os.getenv("GX10_BASE_URL", "http://localhost:8001")
GX10_TIMEOUT_SECONDS = float(os.getenv("GX10_TIMEOUT_SECONDS", "30"))
GX10_ENABLED = os.getenv("GX10_ENABLED", "true").lower() == "true"


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not GX10_ENABLED:
        return None
    url = f"{GX10_BASE_URL}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=GX10_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, ValueError) as exc:
        _LOGGER.warning("GX10 call to %s failed: %s", path, exc)
        return None


def redact_documents(workflow_id: str, documents: list[dict[str, str]]) -> dict[str, Any]:
    """
    Send raw documents to the GX10 for local PII / secret / confidential masking.

    Each document must have keys: id, owner, type, content.

    On success returns the GX10 response dict (with redactedDocuments + redactionLog).
    On failure returns a passthrough envelope where redactedDocuments == documents and
    trustLayerStatus is "skipped", so callers can blindly use response["redactedDocuments"].
    """
    if not documents:
        return {
            "workflowId": workflow_id,
            "ranOn": "GX10_NOOP",
            "trustLayerStatus": "passed",
            "documentsProcessed": 0,
            "sensitiveFieldsRedacted": 0,
            "rawDocumentsSentToCloud": 0,
            "redactedDocuments": [],
            "redactionLog": [],
        }

    payload = {"workflowId": workflow_id, "documents": documents}
    result = _post_json("/api/gx10/redact", payload)
    if result and "redactedDocuments" in result:
        return result

    _LOGGER.error(
        "GX10 redaction unavailable (workflow=%s) — passing %d documents through unredacted. "
        "Set GX10_ENABLED=false to silence this warning if intentional.",
        workflow_id, len(documents),
    )
    return {
        "workflowId": workflow_id,
        "ranOn": "GX10_UNREACHABLE",
        "trustLayerStatus": "skipped",
        "documentsProcessed": len(documents),
        "sensitiveFieldsRedacted": 0,
        "rawDocumentsSentToCloud": len(documents),
        "redactedDocuments": documents,
        "redactionLog": [],
    }


def check_contradictions(workflow_id: str, claims: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Run a local contradiction pre-check on the GX10. Returns None on failure so
    the caller can fall back to the rule engine + Gemini path it already runs.

    Each claim must have keys: owner, role, claim, confidence ("high"|"medium"|"low"),
    sourceIds (list of strings).
    """
    if not claims:
        return None
    payload = {"workflowId": workflow_id, "claims": claims}
    result = _post_json("/api/gx10/contradiction-check", payload)
    if result and "contradictions" in result:
        return result
    return None
