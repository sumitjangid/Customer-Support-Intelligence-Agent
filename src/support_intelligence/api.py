"""HTTP API for the customer support intelligence service."""

from datetime import datetime, timezone
from typing import Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi import status

from support_intelligence.models import (
    TicketReceipt,
    TicketSubmission,
    TicketTriageRequest,
    TicketTriageResult,
    TicketWorkflowResult,
)
from support_intelligence.response_suggestion import (
    ResponseSuggestion,
    ResponseSuggestionError,
    suggest_response,
)
from support_intelligence.retrieval import RetrievalError
from support_intelligence.triage import triage_ticket

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


@app.post(
    "/tickets/triage",
    response_model=TicketTriageResult,
    tags=["tickets"],
)
def triage_support_ticket(ticket: TicketTriageRequest) -> TicketTriageResult:
    """Return classification and urgency recommendations for human review."""
    return triage_ticket(ticket)


@app.post(
    "/tickets/suggest-response",
    response_model=ResponseSuggestion,
    tags=["tickets"],
)
def suggest_ticket_response(ticket: TicketSubmission) -> ResponseSuggestion:
    """Return an evidence-grounded draft; sending always requires agent approval."""
    try:
        return suggest_response(ticket)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local knowledge index is unavailable; index the knowledge base first.",
        ) from exc
    except (ResponseSuggestionError, RetrievalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post(
    "/tickets/process",
    response_model=TicketWorkflowResult,
    tags=["tickets"],
)
def process_ticket_once(ticket: TicketTriageRequest) -> TicketWorkflowResult:
    """Run triage and response suggestion from one ticket submission.

    This endpoint is stateless: the returned ticket ID is only a correlation ID,
    and no ticket or draft is written to storage or sent to a customer.
    """
    triage = triage_ticket(ticket)
    try:
        suggestion = suggest_response(
            TicketSubmission(
                subject=ticket.subject,
                description=ticket.description,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local knowledge index is unavailable; index the knowledge base first.",
        ) from exc
    except (ResponseSuggestionError, RetrievalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return TicketWorkflowResult(
        ticket_id=uuid4(),
        processed_at=datetime.now(timezone.utc),
        triage=triage,
        response_suggestion=suggestion,
    )
