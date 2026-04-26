from pydantic import BaseModel, Field
from typing import List


class Document(BaseModel):
    id: str
    owner: str
    type: str
    content: str


class RedactRequest(BaseModel):
    workflowId: str
    documents: List[Document]


class RedactionLogEntry(BaseModel):
    documentId: str
    type: str
    replacement: str
    reason: str


class RedactResponse(BaseModel):
    workflowId: str
    ranOn: str = "ASUS_GX10"
    trustLayerStatus: str
    documentsProcessed: int
    sensitiveFieldsRedacted: int
    rawDocumentsSentToCloud: int
    redactedDocuments: List[Document]
    redactionLog: List[RedactionLogEntry]


class Claim(BaseModel):
    owner: str
    role: str
    claim: str
    confidence: str
    sourceIds: List[str] = Field(default_factory=list)


class ContradictionCheckRequest(BaseModel):
    workflowId: str
    claims: List[Claim]


class Contradiction(BaseModel):
    severity: str
    between: List[str]
    reason: str
    recommendedAction: str


class CloudSafeClaim(BaseModel):
    owner: str
    claim: str
    confidence: str


class CloudSafeVerifierInput(BaseModel):
    summary: str
    claims: List[CloudSafeClaim]


class ContradictionCheckResponse(BaseModel):
    workflowId: str
    ranOn: str = "ASUS_GX10"
    trustLayerStatus: str
    claimsVerified: int
    contradictionsDetected: int
    contradictions: List[Contradiction]
    confidenceDelta: str
    escalationRequired: bool
    cloudSafeVerifierInput: CloudSafeVerifierInput


class TrustReportPreflight(BaseModel):
    status: str


class TrustReportRedaction(BaseModel):
    documentsProcessed: int
    sensitiveFieldsRedacted: int
    rawDocumentsSentToCloud: int
    durationMs: int


class TrustReportContradiction(BaseModel):
    claimsVerified: int
    contradictionsDetected: int
    escalationRequired: bool
    durationMs: int


class TrustReportDashboardSummary(BaseModel):
    title: str
    status: str
    message: str


class TrustReport(BaseModel):
    workflowId: str
    ranOn: str = "ASUS_GX10"
    preflight: TrustReportPreflight
    redaction: TrustReportRedaction
    contradictionCheck: TrustReportContradiction
    trustLayerStatus: str
    dashboardSummary: TrustReportDashboardSummary
