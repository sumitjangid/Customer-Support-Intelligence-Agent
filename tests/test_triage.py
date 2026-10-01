from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from support_intelligence.api import app
from support_intelligence.models import (
    AccountValue,
    CustomerTier,
    IssueSeverity,
    TicketCategory,
    TicketTriageRequest,
)
from support_intelligence.triage import TriagePolicy, triage_ticket

client = TestClient(app)


@pytest.mark.parametrize(
    "subject,description,category,team",
    [
        ("Refund question", "I was charged twice.", "billing", "billing-support"),
        ("Where is my package?", "Tracking has not updated.", "shipping", "shipping-support"),
        ("Defective item", "The product is broken.", "product", "product-support"),
        ("Need help", "I have a question.", "general", "general-support"),
    ],
)
def test_triage_classifies_and_routes_by_rules(
    subject: str, description: str, category: str, team: str
) -> None:
    response = client.post(
        "/tickets/triage", json={"subject": subject, "description": description}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["category"] == category
    assert result["recommended_team"] == team
    assert result["category_confidence"] in {"low", "medium", "high"}
    assert result["human_review_required"] is False


def test_triage_returns_general_for_ambiguous_category_matches() -> None:
    result = triage_ticket(
        TicketTriageRequest(
            subject="Billing and shipping question",
            description="I need help with billing and shipping.",
        )
    )

    assert result.category.value == "general"
    assert result.category_confidence == "low"
    assert result.recommended_team == "general-support"


def test_priority_score_explains_each_factor_and_clamps_to_100() -> None:
    result = triage_ticket(
        TicketTriageRequest(
            subject="Urgent billing fraud",
            description="Unauthorized charge. I am furious and may close my account.",
            customer_tier=CustomerTier.VIP,
            account_value=AccountValue.HIGH,
            issue_severity=IssueSeverity.CRITICAL,
        )
    )

    assert result.priority_score == 100
    assert result.priority_band.value == "P1"
    assert result.human_review_required is True
    assert result.escalation_reasons == [
        "angry_tone_signal",
        "account_at_risk",
        "suspected_fraud",
    ]
    assert "vip_customer:+10" in result.priority_reasons
    assert "high_account_value:+10" in result.priority_reasons
    assert "suspected_fraud:+20" in result.priority_reasons


def test_explicit_escalation_flags_require_human_review() -> None:
    result = triage_ticket(
        TicketTriageRequest(
            subject="Unexpected payment",
            description="Please investigate this charge.",
            account_at_risk=True,
            suspected_fraud=True,
        )
    )

    assert result.escalation_reasons == ["account_at_risk", "suspected_fraud"]
    assert result.human_review_required is True


def test_custom_policy_can_change_routing_and_category_terms() -> None:
    teams = dict(TriagePolicy().teams)
    teams[TicketCategory.BILLING] = "payments-team"
    policy = TriagePolicy(
        teams=teams,
    )
    result = triage_ticket(
        TicketTriageRequest(subject="Billing refund", description="Please help."),
        policy=policy,
    )

    assert result.recommended_team == "payments-team"


def test_triage_endpoint_rejects_invalid_fields() -> None:
    response = client.post(
        "/tickets/triage",
        json={
            "subject": "Shipping update",
            "description": "Package delayed",
            "customer_email": "not-needed@example.com",
        },
    )

    assert response.status_code == 422
