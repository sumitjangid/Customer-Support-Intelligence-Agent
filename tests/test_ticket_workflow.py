from uuid import UUID

from fastapi.testclient import TestClient

from support_intelligence import api
from support_intelligence.models import (
    ResponseSuggestion,
    TicketTriageRequest,
    TicketWorkflowResult,
)
from support_intelligence.response_suggestion import ResponseSuggestionError

client = TestClient(api.app)


SAMPLE_REQUEST = {
    "subject": "Return window",
    "description": "How long after delivery can I request a return?",
    "customer_reference": "dummy-ref-42",
    "customer_tier": "vip",
    "account_value": "standard",
    "issue_severity": "medium",
}


def test_process_ticket_runs_triage_and_draft_from_one_submission(monkeypatch) -> None:
    observed = {}

    def fake_triage(ticket: TicketTriageRequest):
        observed["triage_ticket"] = ticket
        return {
            "category": "general",
            "category_confidence": "low",
            "matched_category_terms": [],
            "recommended_team": "general-support",
            "priority_score": 40,
            "priority_band": "P3",
            "priority_reasons": ["issue_severity:medium", "vip_customer:+10"],
            "escalation_reasons": [],
            "human_review_required": False,
        }

    def fake_suggest(ticket):
        observed["suggest_ticket"] = ticket
        return ResponseSuggestion(
            status="draft",
            draft_reply="You may request a return within 30 days of delivery.",
            sources=[
                {
                    "source_path": "returns.md",
                    "chunk_index": 0,
                    "chunk_id": "source-chunk-1",
                    "similarity": 0.87,
                }
            ],
            requires_human_review=True,
        )

    monkeypatch.setattr(api, "triage_ticket", fake_triage)
    monkeypatch.setattr(api, "suggest_response", fake_suggest)

    response = client.post("/tickets/process", json=SAMPLE_REQUEST)

    assert response.status_code == 200
    body = response.json()
    UUID(body["ticket_id"])
    assert body["status"] == "processed"
    assert body["processed_at"]
    assert body["triage"]["recommended_team"] == "general-support"
    assert body["response_suggestion"]["status"] == "draft"
    assert body["response_suggestion"]["requires_human_review"] is True
    assert body["response_suggestion"]["sources"][0]["source_path"] == "returns.md"
    assert observed["triage_ticket"].subject == observed["suggest_ticket"].subject
    assert observed["triage_ticket"].description == observed["suggest_ticket"].description
    assert "customer_reference" not in observed["suggest_ticket"].model_dump(exclude_none=True)


def test_process_ticket_returns_abstention_alongside_triage(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "triage_ticket",
        lambda ticket: {
            "category": "general",
            "category_confidence": "low",
            "matched_category_terms": [],
            "recommended_team": "general-support",
            "priority_score": 30,
            "priority_band": "P3",
            "priority_reasons": ["issue_severity:medium"],
            "escalation_reasons": [],
            "human_review_required": False,
        },
    )
    monkeypatch.setattr(
        api,
        "suggest_response",
        lambda ticket: ResponseSuggestion(
            status="abstained",
            abstention_reason="No sufficiently relevant evidence was found.",
            requires_human_review=True,
        ),
    )

    response = client.post("/tickets/process", json=SAMPLE_REQUEST)

    assert response.status_code == 200
    assert response.json()["response_suggestion"]["status"] == "abstained"
    assert response.json()["response_suggestion"]["draft_reply"] is None
    assert response.json()["response_suggestion"]["requires_human_review"] is True


def test_process_ticket_maps_missing_index_to_service_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "triage_ticket",
        lambda ticket: {
            "category": "general",
            "category_confidence": "low",
            "matched_category_terms": [],
            "recommended_team": "general-support",
            "priority_score": 30,
            "priority_band": "P3",
            "priority_reasons": ["issue_severity:medium"],
            "escalation_reasons": [],
            "human_review_required": False,
        },
    )

    def missing_index(ticket):
        raise FileNotFoundError("private local path")

    monkeypatch.setattr(api, "suggest_response", missing_index)
    response = client.post("/tickets/process", json=SAMPLE_REQUEST)

    assert response.status_code == 503
    assert "private local path" not in response.text


def test_process_ticket_maps_gemini_failure_to_gateway_error(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "triage_ticket",
        lambda ticket: {
            "category": "general",
            "category_confidence": "low",
            "matched_category_terms": [],
            "recommended_team": "general-support",
            "priority_score": 30,
            "priority_band": "P3",
            "priority_reasons": ["issue_severity:medium"],
            "escalation_reasons": [],
            "human_review_required": False,
        },
    )

    def provider_failure(ticket):
        raise ResponseSuggestionError("Gemini response generation failed (RateLimitError).")

    monkeypatch.setattr(api, "suggest_response", provider_failure)
    response = client.post("/tickets/process", json=SAMPLE_REQUEST)

    assert response.status_code == 502
    assert response.json()["detail"] == "Gemini response generation failed (RateLimitError)."


def test_process_ticket_validates_the_single_payload() -> None:
    response = client.post(
        "/tickets/process",
        json={"subject": "  ", "description": "synthetic description"},
    )

    assert response.status_code == 422


def test_workflow_response_model_has_nested_schemas() -> None:
    schema = TicketWorkflowResult.model_json_schema()

    assert "triage" in schema["properties"]
    assert "response_suggestion" in schema["properties"]
