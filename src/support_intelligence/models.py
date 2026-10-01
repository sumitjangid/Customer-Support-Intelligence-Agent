"""Validated API models for incoming support tickets."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class TicketSubmission(BaseModel):
    """Customer-provided ticket content accepted by the API."""

    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    customer_reference: Optional[str] = Field(None, min_length=1, max_length=100)

    @validator("subject", "description")
    def reject_blank_text(cls, value: str) -> str:
        """Reject whitespace-only content and normalize outer whitespace."""
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @validator("customer_reference")
    def normalize_customer_reference(cls, value: Optional[str]) -> Optional[str]:
        """Normalize an optional reference without accepting an empty value."""
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    class Config:
        extra = "forbid"


class TicketReceipt(BaseModel):
    """Acknowledgement returned for a validated ticket submission."""

    ticket_id: UUID
    status: str = "received"
    received_at: datetime


class CustomerTier(str, Enum):
    STANDARD = "standard"
    VIP = "vip"


class AccountValue(str, Enum):
    STANDARD = "standard"
    HIGH = "high"


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketTriageRequest(TicketSubmission):
    """Ticket plus bounded triage signals; avoid transmitting account details."""

    customer_tier: CustomerTier = CustomerTier.STANDARD
    account_value: AccountValue = AccountValue.STANDARD
    issue_severity: IssueSeverity = IssueSeverity.MEDIUM
    account_at_risk: bool = False
    suspected_fraud: bool = False


class TicketCategory(str, Enum):
    BILLING = "billing"
    SHIPPING = "shipping"
    PRODUCT = "product"
    GENERAL = "general"


class PriorityBand(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class TicketTriageResult(BaseModel):
    """Recommendation for a support agent; it performs no automatic action."""

    category: TicketCategory
    category_confidence: str
    matched_category_terms: list[str]
    recommended_team: str
    priority_score: int = Field(..., ge=0, le=100)
    priority_band: PriorityBand
    priority_reasons: list[str]
    escalation_reasons: list[str]
    human_review_required: bool


class ResponseSourceReference(BaseModel):
    source_path: str
    chunk_index: int
    chunk_id: str
    similarity: float = Field(..., ge=-1.0, le=1.0)


class ResponseSuggestion(BaseModel):
    """A response draft or abstention, always for human review."""

    status: str
    draft_reply: Optional[str] = None
    sources: list[ResponseSourceReference] = Field(default_factory=list)
    requires_human_review: bool = True
    abstention_reason: Optional[str] = None


class TicketWorkflowResult(BaseModel):
    """Combined stateless ticket analysis response; no ticket is persisted."""

    ticket_id: UUID
    status: str = "processed"
    processed_at: datetime
    triage: TicketTriageResult
    response_suggestion: ResponseSuggestion