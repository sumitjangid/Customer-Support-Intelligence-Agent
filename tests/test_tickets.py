from uuid import UUID

from fastapi.testclient import TestClient

from support_intelligence.api import app

client = TestClient(app)


def test_submit_ticket_returns_receipt_without_echoing_ticket_text() -> None:
    response = client.post(
        "/tickets",
        json={
            "subject": "  Package has not arrived  ",
            "description": "  Tracking has not changed for three days.  ",
            "customer_reference": "  customer-123  ",
        },
    )

    assert response.status_code == 201
    receipt = response.json()
    UUID(receipt["ticket_id"])
    assert receipt["status"] == "received"
    assert receipt["received_at"]
    assert "description" not in receipt


def test_submit_ticket_rejects_blank_subject() -> None:
    response = client.post(
        "/tickets",
        json={"subject": "  ", "description": "A package is late."},
    )

    assert response.status_code == 422


def test_submit_ticket_rejects_missing_description() -> None:
    response = client.post("/tickets", json={"subject": "Billing question"})

    assert response.status_code == 422


def test_submit_ticket_rejects_unrecognized_fields() -> None:
    response = client.post(
        "/tickets",
        json={
            "subject": "Billing question",
            "description": "I was charged twice.",
            "email": "customer@example.com",
        },
    )

    assert response.status_code == 422