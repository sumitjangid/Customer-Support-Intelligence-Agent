from pathlib import Path

import pytest

from support_intelligence.evaluate import DEFAULT_DATASET, evaluate_dataset


def test_synthetic_triage_dataset_passes_all_labeled_cases() -> None:
    summary = evaluate_dataset(DEFAULT_DATASET)

    assert summary.total_cases == 10
    assert summary.passed_cases == 10
    assert summary.passed is True
    assert summary.category_accuracy == pytest.approx(1.0)
    assert summary.team_accuracy == pytest.approx(1.0)
    assert summary.priority_band_accuracy == pytest.approx(1.0)
    assert summary.escalation_exact_match == pytest.approx(1.0)
    assert summary.human_review_accuracy == pytest.approx(1.0)
    assert summary.failed_case_ids == []


def test_evaluation_rejects_malformed_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "cases.json"
    dataset.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty JSON array"):
        evaluate_dataset(dataset)
