"""HTTP API for the customer support intelligence service."""

from datetime import datetime, timezone
from typing import Dict
from uuid import uuid4

from fastapi import FastAPI
from fastapi import status

from support_intelligence.models import TicketReceipt, TicketSubmission

app = FastAPI(
    title="Customer Support Intelligence Agent",
    description=(
        "A human-reviewed support assistant for knowledge retrieval, "
        "ticket triage, and response suggestions."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["operations"])
def health_check() -> Dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}


@app.post(
    "/tickets",
    response_model=TicketReceipt,
    status_code=status.HTTP_201_CREATED,
    tags=["tickets"],
)
def submit_ticket(ticket: TicketSubmission) -> TicketReceipt:
    """Validate and acknowledge a ticket without persisting its contents."""
    return TicketReceipt(
        ticket_id=uuid4(),
        status="received",
        received_at=datetime.now(timezone.utc),
    )
