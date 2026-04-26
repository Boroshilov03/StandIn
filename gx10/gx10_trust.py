"""Deterministic trust-layer logic: regex redaction + rule-based contradiction detection."""
import re
from typing import Iterable

KNOWN_CUSTOMERS = [
    "ACME",
    "Globex",
    "Initech",
    "Umbrella",
    "Stark Industries",
    "Wayne Enterprises",
    "Soylent",
    "Hooli",
    "Pied Piper",
]

CONFIDENTIAL_PHRASES = [
    "confidential pricing",
    "draft pricing",
    "confidential",
    "legal-risk",
    "legal risk",
    "security incident",
]

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+", re.IGNORECASE)
API_TOKEN_PATTERN = re.compile(r"\b(?:sk|pk|api|tok)[-_][a-zA-Z0-9\-_]{6,}\b")


BLOCKED_TERMS = [
    "blocked",
    "blocker",
    "failing",
    "unstable",
    "not ready",
    "delayed",
    "broken",
    "waiting",
    "regressed",
    "down",
]
READY_TERMS = [
    "ready",
    "finalized",
    "launch today",
    "approved",
    "complete",
    "completed",
    "no blockers",
    "shipped",
    "done",
]


def _redact_one(content: str, doc_id: str) -> tuple[str, list[dict]]:
    log: list[dict] = []
    redacted = content

    for match in API_TOKEN_PATTERN.findall(redacted):
        log.append({
            "documentId": doc_id,
            "type": "secret",
            "replacement": "[SECRET_REDACTED]",
            "reason": "Potential API token or credential.",
        })
    redacted = API_TOKEN_PATTERN.sub("[SECRET_REDACTED]", redacted)

    for match in BEARER_PATTERN.findall(redacted):
        log.append({
            "documentId": doc_id,
            "type": "secret",
            "replacement": "[SECRET_REDACTED]",
            "reason": "Bearer authorization token.",
        })
    redacted = BEARER_PATTERN.sub("[SECRET_REDACTED]", redacted)

    for match in EMAIL_PATTERN.findall(redacted):
        log.append({
            "documentId": doc_id,
            "type": "email",
            "replacement": "[EMAIL_REDACTED]",
            "reason": "Personal email address.",
        })
    redacted = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", redacted)

    for match in PHONE_PATTERN.findall(redacted):
        log.append({
            "documentId": doc_id,
            "type": "phone",
            "replacement": "[PHONE_REDACTED]",
            "reason": "Phone number.",
        })
    redacted = PHONE_PATTERN.sub("[PHONE_REDACTED]", redacted)

    for match in CVE_PATTERN.findall(redacted):
        log.append({
            "documentId": doc_id,
            "type": "cve",
            "replacement": "[CVE_REDACTED]",
            "reason": "Security vulnerability identifier.",
        })
    redacted = CVE_PATTERN.sub("[CVE_REDACTED]", redacted)

    for customer in KNOWN_CUSTOMERS:
        pattern = re.compile(rf"\b{re.escape(customer)}\b", re.IGNORECASE)
        if pattern.search(redacted):
            log.append({
                "documentId": doc_id,
                "type": "customer_name",
                "replacement": "[CUSTOMER_REDACTED]",
                "reason": "Customer identifier should not be sent to cloud reasoning layer.",
            })
            redacted = pattern.sub("[CUSTOMER_REDACTED]", redacted)

    for phrase in CONFIDENTIAL_PHRASES:
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
        if pattern.search(redacted):
            log.append({
                "documentId": doc_id,
                "type": "confidential",
                "replacement": "[CONFIDENTIAL_REDACTED]",
                "reason": "Confidential business language.",
            })
            redacted = pattern.sub("[CONFIDENTIAL_REDACTED]", redacted)

    return redacted, log


def deterministic_redact(workflow_id: str, documents: list[dict]) -> dict:
    redacted_docs: list[dict] = []
    full_log: list[dict] = []

    for doc in documents:
        new_content, doc_log = _redact_one(doc["content"], doc["id"])
        redacted_docs.append({
            "id": doc["id"],
            "owner": doc["owner"],
            "type": doc["type"],
            "content": new_content,
        })
        full_log.extend(doc_log)

    return {
        "workflowId": workflow_id,
        "ranOn": "ASUS_GX10",
        "trustLayerStatus": "passed",
        "documentsProcessed": len(documents),
        "sensitiveFieldsRedacted": len(full_log),
        "rawDocumentsSentToCloud": 0,
        "redactedDocuments": redacted_docs,
        "redactionLog": full_log,
    }


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    lowered = text.lower()
    return [t for t in terms if t in lowered]


def _severity(owner_a: str, owner_b: str) -> str:
    pair = {owner_a, owner_b}
    if {"Engineering", "GTM"}.issubset(pair):
        return "high"
    if "Engineering" in pair:
        return "high"
    return "medium"


def deterministic_contradictions(workflow_id: str, claims: list[dict]) -> dict:
    contradictions: list[dict] = []

    for i, a in enumerate(claims):
        for b in claims[i + 1 :]:
            a_blocked = _contains_any(a["claim"], BLOCKED_TERMS)
            b_ready = _contains_any(b["claim"], READY_TERMS)
            b_blocked = _contains_any(b["claim"], BLOCKED_TERMS)
            a_ready = _contains_any(a["claim"], READY_TERMS)

            mismatch = (a_blocked and b_ready) or (b_blocked and a_ready)
            if not mismatch:
                continue

            if a_blocked and b_ready:
                blocked_owner, ready_owner = a["owner"], b["owner"]
                blocked_claim, ready_claim = a["claim"], b["claim"]
            else:
                blocked_owner, ready_owner = b["owner"], a["owner"]
                blocked_claim, ready_claim = b["claim"], a["claim"]

            severity = _severity(blocked_owner, ready_owner)
            contradictions.append({
                "severity": severity,
                "between": [blocked_owner, ready_owner],
                "reason": f"{ready_owner} says {ready_claim.strip().rstrip('.')}, but {blocked_owner} says {blocked_claim.strip().rstrip('.')}.",
                "recommendedAction": f"Escalate to {blocked_owner} and {ready_owner} for a 15-minute launch readiness decision.",
            })

    has_high = any(c["severity"] == "high" for c in contradictions)
    escalation_required = bool(has_high)

    has_empty_sources = any(not c.get("sourceIds") for c in claims)
    if contradictions:
        confidence_delta = "high" if has_high else "medium"
    else:
        confidence_delta = "low" if has_empty_sources else "none"

    cloud_safe_claims = [
        {"owner": c["owner"], "claim": c["claim"], "confidence": c["confidence"]}
        for c in claims
    ]
    summary_parts = []
    for c in claims:
        if _contains_any(c["claim"], BLOCKED_TERMS):
            summary_parts.append(f"{c['owner']} reports a blocker.")
        elif _contains_any(c["claim"], READY_TERMS):
            summary_parts.append(f"{c['owner']} reports readiness.")
        else:
            summary_parts.append(f"{c['owner']} reports a status update.")
    summary = " ".join(summary_parts) if summary_parts else "No claims provided."

    return {
        "workflowId": workflow_id,
        "ranOn": "ASUS_GX10",
        "trustLayerStatus": "passed",
        "claimsVerified": len(claims),
        "contradictionsDetected": len(contradictions),
        "contradictions": contradictions,
        "confidenceDelta": confidence_delta,
        "escalationRequired": escalation_required,
        "cloudSafeVerifierInput": {
            "summary": summary,
            "claims": cloud_safe_claims,
        },
    }


REDACT_SYSTEM_PROMPT = (
    "You are a privacy redaction layer running on a trusted edge device. "
    "You strip sensitive content (customer names, secrets, confidential business language, "
    "credentials, PII) from documents before they go to a cloud LLM. "
    "Always reply with strict JSON matching the requested schema."
)

CONTRADICTION_SYSTEM_PROMPT = (
    "You are a contradiction detector running on a trusted edge device. "
    "Compare structured claims from multiple delegate agents and flag contradictions, "
    "especially launch-blocking ones. Always reply with strict JSON matching the schema."
)


def build_redact_prompt(workflow_id: str, documents: list[dict]) -> str:
    return (
        "Redact sensitive content from each document. Replace customer names with "
        "[CUSTOMER_REDACTED], credentials/tokens with [SECRET_REDACTED], confidential "
        "language with [CONFIDENTIAL_REDACTED], emails with [EMAIL_REDACTED]. "
        "Return JSON with keys: workflowId, ranOn ('ASUS_GX10'), trustLayerStatus ('passed'), "
        "documentsProcessed, sensitiveFieldsRedacted, rawDocumentsSentToCloud (0), "
        "redactedDocuments (list of {id,owner,type,content}), redactionLog "
        "(list of {documentId,type,replacement,reason}).\n\n"
        f"workflowId: {workflow_id}\n"
        f"documents: {documents}"
    )


def build_contradiction_prompt(workflow_id: str, claims: list[dict]) -> str:
    return (
        "Detect contradictions between these delegate claims. A contradiction exists when "
        "one claim says blocked/failing/delayed and another says ready/finalized/complete. "
        "Engineering-vs-GTM mismatches are high severity. Return JSON with keys: workflowId, "
        "ranOn ('ASUS_GX10'), trustLayerStatus ('passed'), claimsVerified, "
        "contradictionsDetected, contradictions (list of {severity,between,reason,recommendedAction}), "
        "confidenceDelta, escalationRequired (bool), cloudSafeVerifierInput "
        "({summary, claims:[{owner,claim,confidence}]}).\n\n"
        f"workflowId: {workflow_id}\n"
        f"claims: {claims}"
    )
