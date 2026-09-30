"""Validated API models for incoming support tickets."""

from datetime import datetime
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