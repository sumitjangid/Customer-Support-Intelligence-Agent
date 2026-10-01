"""Deterministic ticket classification, priority, and escalation recommendations."""

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

from support_intelligence.models import (
    AccountValue,
    CustomerTier,
    IssueSeverity,
    PriorityBand,
    TicketCategory,
    TicketTriageRequest,
    TicketTriageResult,
)


@dataclass(frozen=True)
class TriagePolicy:
    """Editable prototype rules; review and tune against real evaluation cases."""

    category_terms: Mapping[TicketCategory, Tuple[str, ...]] = field(
        default_factory=lambda: {
            TicketCategory.BILLING: (
                "billing", "invoice", "charged", "charge", "refund", "payment",
                "subscription", "duplicate charge",
            ),
            TicketCategory.SHIPPING: (
                "shipping", "shipment", "delivery", "delivered", "tracking",
                "package", "parcel", "late", "not arrived",
            ),
            TicketCategory.PRODUCT: (
                "product", "item", "broken", "defective", "damaged", "not working",
                "replacement", "warranty",
            ),
        }
    )
    teams: Mapping[TicketCategory, str] = field(
        default_factory=lambda: {
            TicketCategory.BILLING: "billing-support",
            TicketCategory.SHIPPING: "shipping-support",
            TicketCategory.PRODUCT: "product-support",
            TicketCategory.GENERAL: "general-support",
        }
    )
    angry_terms: Tuple[str, ...] = (
        "angry", "furious", "unacceptable", "outraged", "never again",
        "cancel my account", "lawyer", "lawsuit",
    )
    account_risk_terms: Tuple[str, ...] = (
        "close my account", "cancel my account", "cancel my subscription",
        "leaving your service", "switch to a competitor",
    )
    fraud_terms: Tuple[str, ...] = (
        "fraud", "unauthorized charge", "stolen card", "account hacked",
        "identity theft", "did not authorize",
    )
    severity_points: Mapping[IssueSeverity, int] = field(
        default_factory=lambda: {
            IssueSeverity.LOW: 10,
            IssueSeverity.MEDIUM: 30,
            IssueSeverity.HIGH: 55,
            IssueSeverity.CRITICAL: 75,
        }
    )
    vip_points: int = 10
    high_account_value_points: int = 10
    account_risk_points: int = 10
    fraud_points: int = 20
    angry_tone_points: int = 5
    p1_threshold: int = 75
    p2_threshold: int = 50
    p3_threshold: int = 25


def _find_terms(text: str, terms: Tuple[str, ...]) -> Tuple[str, ...]:
    lowered = text.casefold()
    return tuple(term for term in terms if term in lowered)


def _classify(text: str, policy: TriagePolicy) -> Tuple[TicketCategory, Tuple[str, ...], str]:
    matches: Dict[TicketCategory, Tuple[str, ...]] = {
        category: _find_terms(text, terms)
        for category, terms in policy.category_terms.items()
    }
    scores = {category: len(terms) for category, terms in matches.items()}
    best_score = max(scores.values(), default=0)
    winners = [category for category, score in scores.items() if score == best_score and score]

    if best_score == 0 or len(winners) != 1:
        matched = tuple(
            term for category in winners for term in matches[category]
        )
        return TicketCategory.GENERAL, matched, "low"

    winner = winners[0]
    confidence = "high" if best_score >= 2 else "medium"
    return winner, matches[winner], confidence


def triage_ticket(
    ticket: TicketTriageRequest, policy: Optional[TriagePolicy] = None
) -> TicketTriageResult:
    """Return auditable recommendations without contacting an AI provider.

    Text keyword matches are heuristic indicators, not sentiment analysis or a
    fraud decision. Explicit request flags and all recommendations require
    human verification before action.
    """
    if policy is None:
        policy = TriagePolicy()

    text = "{}\n{}".format(ticket.subject, ticket.description)
    category, matched_terms, confidence = _classify(text, policy)
    team = policy.teams.get(category, policy.teams[TicketCategory.GENERAL])

    angry_matches = _find_terms(text, policy.angry_terms)
    risk_matches = _find_terms(text, policy.account_risk_terms)
    fraud_matches = _find_terms(text, policy.fraud_terms)

    escalation_reasons = []
    if angry_matches:
        escalation_reasons.append("angry_tone_signal")
    if ticket.account_at_risk or risk_matches:
        escalation_reasons.append("account_at_risk")
    if ticket.suspected_fraud or fraud_matches:
        escalation_reasons.append("suspected_fraud")

    score = policy.severity_points[ticket.issue_severity]
    priority_reasons = ["issue_severity:{}".format(ticket.issue_severity.value)]
    if ticket.customer_tier == CustomerTier.VIP:
        score += policy.vip_points
        priority_reasons.append("vip_customer:+{}".format(policy.vip_points))
    if ticket.account_value == AccountValue.HIGH:
        score += policy.high_account_value_points
        priority_reasons.append("high_account_value:+{}".format(policy.high_account_value_points))
    if "account_at_risk" in escalation_reasons:
        score += policy.account_risk_points
        priority_reasons.append("account_at_risk:+{}".format(policy.account_risk_points))
    if "suspected_fraud" in escalation_reasons:
        score += policy.fraud_points
        priority_reasons.append("suspected_fraud:+{}".format(policy.fraud_points))
    if "angry_tone_signal" in escalation_reasons:
        score += policy.angry_tone_points
        priority_reasons.append("angry_tone_signal:+{}".format(policy.angry_tone_points))

    score = min(score, 100)
    if score >= policy.p1_threshold:
        band = PriorityBand.P1
    elif score >= policy.p2_threshold:
        band = PriorityBand.P2
    elif score >= policy.p3_threshold:
        band = PriorityBand.P3
    else:
        band = PriorityBand.P4

    return TicketTriageResult(
        category=category,
        category_confidence=confidence,
        matched_category_terms=list(matched_terms),
        recommended_team=team,
        priority_score=score,
        priority_band=band,
        priority_reasons=priority_reasons,
        escalation_reasons=escalation_reasons,
        human_review_required=band == PriorityBand.P1 or bool(escalation_reasons),
    )
