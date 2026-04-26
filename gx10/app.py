"""StandIn GX10 Edge Trust Layer — FastAPI service.

Runs locally on ASUS Ascent GX10. Performs privacy redaction + contradiction
pre-check before workplace context is sent to cloud reasoning (Gemini).
"""
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

load_dotenv()

import gx10_trust
import mock_outputs
import ollama_client
from models import (
    ContradictionCheckRequest,
    ContradictionCheckResponse,
    RedactRequest,
    RedactResponse,
    TrustReport,
)

GX10_MOCK = os.getenv("GX10_MOCK", "true").lower() == "true"
PORT = int(os.getenv("PORT", "8001"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("standin-gx10")

app = FastAPI(title="standin-gx10", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS: dict[str, dict] = {}


def _validate_redact(payload: dict) -> bool:
    required = {"redactedDocuments", "redactionLog", "documentsProcessed"}
    return isinstance(payload, dict) and required.issubset(payload.keys())


def _validate_contradiction(payload: dict) -> bool:
    required = {"contradictions", "claimsVerified", "escalationRequired"}
    return isinstance(payload, dict) and required.issubset(payload.keys())


def _store_report(workflow_id: str, redact: dict | None, contradiction: dict | None,
                  redact_ms: int, contradiction_ms: int) -> None:
    existing = REPORTS.get(workflow_id, {
        "workflowId": workflow_id,
        "ranOn": "ASUS_GX10",
        "preflight": {"status": "skipped"},
        "redaction": {
            "documentsProcessed": 0,
            "sensitiveFieldsRedacted": 0,
            "rawDocumentsSentToCloud": 0,
            "durationMs": 0,
        },
        "contradictionCheck": {
            "claimsVerified": 0,
            "contradictionsDetected": 0,
            "escalationRequired": False,
            "durationMs": 0,
        },
        "trustLayerStatus": "passed",
        "dashboardSummary": {
            "title": "GX10 Trust Layer — Private Edge Verification",
            "status": "Complete",
            "message": "Raw workplace context was redacted locally before cloud reasoning. Agent claims were checked locally before final synthesis.",
        },
    })

    if redact is not None:
        existing["redaction"] = {
            "documentsProcessed": redact.get("documentsProcessed", 0),
            "sensitiveFieldsRedacted": redact.get("sensitiveFieldsRedacted", 0),
            "rawDocumentsSentToCloud": redact.get("rawDocumentsSentToCloud", 0),
            "durationMs": redact_ms,
        }
    if contradiction is not None:
        existing["contradictionCheck"] = {
            "claimsVerified": contradiction.get("claimsVerified", 0),
            "contradictionsDetected": contradiction.get("contradictionsDetected", 0),
            "escalationRequired": contradiction.get("escalationRequired", False),
            "durationMs": contradiction_ms,
        }
    REPORTS[workflow_id] = existing


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "standin-gx10", "ranOn": "ASUS_GX10"}


@app.post("/api/gx10/redact", response_model=RedactResponse)
def redact(req: RedactRequest) -> RedactResponse:
    start = time.perf_counter()
    workflow_id = req.workflowId
    documents = [d.model_dump() for d in req.documents]

    deterministic = gx10_trust.deterministic_redact(workflow_id, documents)
    result = deterministic
    mode = "deterministic"

    if not GX10_MOCK:
        try:
            llm_payload = ollama_client.generate_json(
                prompt=gx10_trust.build_redact_prompt(workflow_id, documents),
                system=gx10_trust.REDACT_SYSTEM_PROMPT,
            )
        except Exception as e:
            logger.warning("redact[%s] gemma call raised: %s; using deterministic", workflow_id, e)
            llm_payload = None

        if llm_payload is None:
            mode = "fallback_deterministic"
            logger.info("redact[%s] gemma unavailable or returned no JSON; using deterministic", workflow_id)
        elif not _validate_redact(llm_payload):
            mode = "fallback_deterministic"
            logger.info("redact[%s] gemma payload missing required keys; using deterministic", workflow_id)
        else:
            llm_payload["workflowId"] = workflow_id
            llm_payload["ranOn"] = "ASUS_GX10"
            llm_payload["trustLayerStatus"] = "passed"
            llm_payload.setdefault("rawDocumentsSentToCloud", 0)
            try:
                RedactResponse(**llm_payload)
                result = llm_payload
                mode = "gemma_refined"
            except (ValidationError, TypeError, ValueError) as e:
                mode = "fallback_deterministic"
                logger.warning("redact[%s] gemma payload failed schema validation: %s; using deterministic", workflow_id, e)

    try:
        response = RedactResponse(**result)
    except (ValidationError, TypeError, ValueError) as e:
        logger.error("redact[%s] deterministic failed schema validation: %s; using mock", workflow_id, e)
        result = mock_outputs.mock_redact_response(workflow_id, documents)
        response = RedactResponse(**result)
        mode = "mock_fallback"

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    _store_report(workflow_id, result, None, elapsed_ms, 0)
    logger.info("redact[%s] mode=%s elapsedMs=%d", workflow_id, mode, elapsed_ms)
    return response


@app.post("/api/gx10/contradiction-check", response_model=ContradictionCheckResponse)
def contradiction_check(req: ContradictionCheckRequest) -> ContradictionCheckResponse:
    start = time.perf_counter()
    workflow_id = req.workflowId
    claims = [c.model_dump() for c in req.claims]

    deterministic = gx10_trust.deterministic_contradictions(workflow_id, claims)
    result = deterministic
    mode = "deterministic"

    if not GX10_MOCK:
        try:
            llm_payload = ollama_client.generate_json(
                prompt=gx10_trust.build_contradiction_prompt(workflow_id, claims),
                system=gx10_trust.CONTRADICTION_SYSTEM_PROMPT,
            )
        except Exception as e:
            logger.warning("contradiction[%s] gemma call raised: %s; using deterministic", workflow_id, e)
            llm_payload = None

        if llm_payload is None:
            mode = "fallback_deterministic"
            logger.info("contradiction[%s] gemma unavailable or returned no JSON; using deterministic", workflow_id)
        elif not _validate_contradiction(llm_payload):
            mode = "fallback_deterministic"
            logger.info("contradiction[%s] gemma payload missing required keys; using deterministic", workflow_id)
        else:
            llm_payload["workflowId"] = workflow_id
            llm_payload["ranOn"] = "ASUS_GX10"
            llm_payload["trustLayerStatus"] = "passed"
            llm_payload.setdefault("claimsVerified", len(claims))
            llm_payload.setdefault("cloudSafeVerifierInput", deterministic["cloudSafeVerifierInput"])
            llm_payload.setdefault("confidenceDelta", deterministic["confidenceDelta"])
            try:
                ContradictionCheckResponse(**llm_payload)
                result = llm_payload
                mode = "gemma_refined"
            except (ValidationError, TypeError, ValueError) as e:
                mode = "fallback_deterministic"
                logger.warning("contradiction[%s] gemma payload failed schema validation: %s; using deterministic", workflow_id, e)

    try:
        response = ContradictionCheckResponse(**result)
    except (ValidationError, TypeError, ValueError) as e:
        logger.error("contradiction[%s] deterministic failed schema validation: %s; using mock", workflow_id, e)
        result = mock_outputs.mock_contradiction_response(workflow_id, claims)
        response = ContradictionCheckResponse(**result)
        mode = "mock_fallback"

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    _store_report(workflow_id, None, result, 0, elapsed_ms)
    logger.info("contradiction[%s] mode=%s elapsedMs=%d", workflow_id, mode, elapsed_ms)
    return response


@app.get("/api/gx10/trust-report/{workflow_id}", response_model=TrustReport)
def trust_report(workflow_id: str) -> TrustReport:
    if workflow_id in REPORTS:
        return TrustReport(**REPORTS[workflow_id])
    return TrustReport(**mock_outputs.mock_trust_report(workflow_id))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
