"""Run deterministic offline ticket-triage evaluation against labeled synthetic cases."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from support_intelligence.models import TicketTriageRequest
from support_intelligence.triage import triage_ticket

DEFAULT_DATASET = Path("evaluation/triage-cases.json")


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category_correct: bool
    team_correct: bool
    priority_correct: bool
    escalation_flags_correct: bool
    human_review_correct: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.category_correct,
                self.team_correct,
                self.priority_correct,
                self.escalation_flags_correct,
                self.human_review_correct,
            )
        )


@dataclass(frozen=True)
class EvaluationSummary:
    dataset: str
    total_cases: int
    category_accuracy: float
    team_accuracy: float
    priority_band_accuracy: float
    escalation_exact_match: float
    human_review_accuracy: float
    passed_cases: int
    failed_case_ids: List[str]

    @property
    def passed(self) -> bool:
        return self.passed_cases == self.total_cases


def _load_cases(path: Path) -> List[Dict[str, Any]]:
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Could not read evaluation dataset: {}".format(path)) from exc
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation dataset must be a non-empty JSON array.")
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not case.get("id") or not isinstance(case.get("ticket"), dict):
            raise ValueError("Evaluation case {} must include id and ticket objects.".format(index))
        for field in (
            "expected_category",
            "expected_team",
            "expected_priority_band",
            "expected_escalations",
            "expected_human_review",
        ):
            if field not in case:
                raise ValueError(
                    "Evaluation case {!r} is missing {!r}.".format(case.get("id"), field)
                )
    return cases


def evaluate_dataset(path: Path = DEFAULT_DATASET) -> EvaluationSummary:
    """Compute exact-match metrics for deterministic policy behavior, no APIs called."""
    cases = _load_cases(Path(path))
    results = []
    for case in cases:
        request = TicketTriageRequest(**case["ticket"])
        actual = triage_ticket(request)
        results.append(
            CaseResult(
                case_id=case["id"],
                category_correct=actual.category.value == case["expected_category"],
                team_correct=actual.recommended_team == case["expected_team"],
                priority_correct=actual.priority_band.value == case["expected_priority_band"],
                escalation_flags_correct=set(actual.escalation_reasons)
                == set(case["expected_escalations"]),
                human_review_correct=actual.human_review_required
                == case["expected_human_review"],
            )
        )

    count = len(results)
    return EvaluationSummary(
        dataset=str(path),
        total_cases=count,
        category_accuracy=sum(result.category_correct for result in results) / count,
        team_accuracy=sum(result.team_correct for result in results) / count,
        priority_band_accuracy=sum(result.priority_correct for result in results) / count,
        escalation_exact_match=sum(result.escalation_flags_correct for result in results) / count,
        human_review_accuracy=sum(result.human_review_correct for result in results) / count,
        passed_cases=sum(result.passed for result in results),
        failed_case_ids=[result.case_id for result in results if not result.passed],
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate deterministic triage rules on a local synthetic dataset."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json", action="store_true", help="print JSON summary")
    args = parser.parse_args(argv)

    try:
        summary = evaluate_dataset(args.dataset)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    data = asdict(summary)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print("Offline triage evaluation (synthetic data)")
        print("Dataset: {}".format(summary.dataset))
        print("Cases passed: {}/{}".format(summary.passed_cases, summary.total_cases))
        print("Category accuracy: {:.0%}".format(summary.category_accuracy))
        print("Team accuracy: {:.0%}".format(summary.team_accuracy))
        print("Priority-band accuracy: {:.0%}".format(summary.priority_band_accuracy))
        print("Escalation exact match: {:.0%}".format(summary.escalation_exact_match))
        print("Human-review accuracy: {:.0%}".format(summary.human_review_accuracy))
        if summary.failed_case_ids:
            print("Failed case IDs: {}".format(", ".join(summary.failed_case_ids)))
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
