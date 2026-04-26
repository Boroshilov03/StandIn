"""Deterministic mock outputs for demo stability when Ollama is unavailable."""


def mock_redact_response(workflow_id: str, documents: list[dict]) -> dict:
    return {
        "workflowId": workflow_id,
        "ranOn": "ASUS_GX10",
        "trustLayerStatus": "passed",
        "documentsProcessed": 2,
        "sensitiveFieldsRedacted": 3,
        "rawDocumentsSentToCloud": 0,
        "redactedDocuments": [
            {
                "id": "slack_eng_1",
                "owner": "Engineering",
                "type": "slack",
                "content": "Auth API is blocked. Customer [CUSTOMER_REDACTED] is affected. Token [SECRET_REDACTED] was exposed.",
            },
            {
                "id": "jira_gtm_1",
                "owner": "GTM",
                "type": "jira",
                "content": "Press release is ready, but legal has not approved the [CONFIDENTIAL_REDACTED] language.",
            },
        ],
        "redactionLog": [
            {
                "documentId": "slack_eng_1",
                "type": "customer_name",
                "replacement": "[CUSTOMER_REDACTED]",
                "reason": "Customer identifier should not be sent to cloud reasoning layer.",
            },
            {
                "documentId": "slack_eng_1",
                "type": "secret",
                "replacement": "[SECRET_REDACTED]",
                "reason": "Potential API token or credential.",
            },
            {
                "documentId": "jira_gtm_1",
                "type": "confidential",
                "replacement": "[CONFIDENTIAL_REDACTED]",
                "reason": "Confidential business language.",
            },
        ],
    }


def mock_contradiction_response(workflow_id: str, claims: list[dict]) -> dict:
    return {
        "workflowId": workflow_id,
        "ranOn": "ASUS_GX10",
        "trustLayerStatus": "passed",
        "claimsVerified": 3,
        "contradictionsDetected": 1,
        "contradictions": [
            {
                "severity": "high",
                "between": ["Engineering", "GTM"],
                "reason": "GTM says launch is ready today, but Engineering says the API is blocked until Friday.",
                "recommendedAction": "Escalate to Engineering and GTM for a 15-minute launch readiness decision.",
            }
        ],
        "confidenceDelta": "high",
        "escalationRequired": True,
        "cloudSafeVerifierInput": {
            "summary": "Engineering reports a critical API blocker. GTM reports launch readiness. Design reports no blocker.",
            "claims": [
                {
                    "owner": "Engineering",
                    "claim": "The API is blocked until Friday.",
                    "confidence": "high",
                },
                {
                    "owner": "GTM",
                    "claim": "Launch is ready today and sales has been briefed.",
                    "confidence": "medium",
                },
                {
                    "owner": "Design",
                    "claim": "Launch page is finalized and handed off.",
                    "confidence": "high",
                },
            ],
        },
    }


def mock_trust_report(workflow_id: str) -> dict:
    return {
        "workflowId": workflow_id,
        "ranOn": "ASUS_GX10",
        "preflight": {"status": "skipped"},
        "redaction": {
            "documentsProcessed": 7,
            "sensitiveFieldsRedacted": 5,
            "rawDocumentsSentToCloud": 0,
            "durationMs": 420,
        },
        "contradictionCheck": {
            "claimsVerified": 9,
            "contradictionsDetected": 1,
            "escalationRequired": True,
            "durationMs": 610,
        },
        "trustLayerStatus": "passed",
        "dashboardSummary": {
            "title": "GX10 Trust Layer — Private Edge Verification",
            "status": "Complete",
            "message": "Raw workplace context was redacted locally before cloud reasoning. Agent claims were checked locally before final synthesis.",
        },
    }
