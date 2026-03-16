from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List

import pytest

from core.analysis.client_risk_timeline import HIGH_RISK_THRESHOLD, analyze_client_risk_timeline
from core.domain.payroll_run import PayrollRun


# ---------------------------------------------------------------------------
# Test helper
# ---------------------------------------------------------------------------


def _run(
    period_end: date,
    risk_score: float = 0.0,
    findings: list | None = None,
) -> PayrollRun:
    """Build a PayrollRun without touching the in-memory store."""
    return PayrollRun(
        run_id=str(uuid.uuid4()),
        client_id="TEST_CLIENT",
        period_start=date(period_end.year, period_end.month, 1),
        period_end=period_end,
        dataset_hash="test_hash",
        normalized_rows=[],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        risk_score=risk_score,
        findings=findings or [],
    )


def _finding(rule_id: str, severity: str = "HIGH") -> dict:
    return {"rule_id": rule_id, "severity": severity}


# ---------------------------------------------------------------------------
# Stable risk
# ---------------------------------------------------------------------------


class TestStableRisk:
    def test_identical_scores_are_stable(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=20.0),
            _run(date(2024, 2, 29), risk_score=20.0),
            _run(date(2024, 3, 31), risk_score=20.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "STABLE"

    def test_mixed_direction_is_stable(self):
        # Scores go up then down — no consistent direction → STABLE
        runs = [
            _run(date(2024, 1, 31), risk_score=10.0),
            _run(date(2024, 2, 29), risk_score=30.0),
            _run(date(2024, 3, 31), risk_score=15.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "STABLE"

    def test_down_then_up_is_stable(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=40.0),
            _run(date(2024, 2, 29), risk_score=20.0),
            _run(date(2024, 3, 31), risk_score=35.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "STABLE"

    def test_empty_input_is_stable(self):
        result = analyze_client_risk_timeline([])
        assert result["risk_trend"] == "STABLE"
        assert result["runs_analyzed"] == 0
        assert result["average_risk_score"] == 0.0
        assert result["high_risk_runs"] == 0
        assert result["most_common_violations"] == []


# ---------------------------------------------------------------------------
# Increasing risk
# ---------------------------------------------------------------------------


class TestIncreasingRisk:
    def test_three_runs_strictly_increasing(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=10.0),
            _run(date(2024, 2, 29), risk_score=30.0),
            _run(date(2024, 3, 31), risk_score=60.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "INCREASING"

    def test_two_runs_increasing(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=5.0),
            _run(date(2024, 2, 29), risk_score=25.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "INCREASING"

    def test_trend_uses_only_last_three_runs(self):
        # First run has high score (would break increasing if included)
        runs = [
            _run(date(2024, 1, 31), risk_score=100.0),  # outside trend window
            _run(date(2024, 2, 29), risk_score=10.0),
            _run(date(2024, 3, 31), risk_score=20.0),
            _run(date(2024, 4, 30), risk_score=40.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "INCREASING"

    def test_unsorted_input_still_detects_increasing(self):
        # Provide runs out of period_end order
        runs = [
            _run(date(2024, 3, 31), risk_score=60.0),
            _run(date(2024, 1, 31), risk_score=10.0),
            _run(date(2024, 2, 29), risk_score=30.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "INCREASING"


# ---------------------------------------------------------------------------
# Decreasing risk
# ---------------------------------------------------------------------------


class TestDecreasingRisk:
    def test_three_runs_strictly_decreasing(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=80.0),
            _run(date(2024, 2, 29), risk_score=40.0),
            _run(date(2024, 3, 31), risk_score=10.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "DECREASING"

    def test_two_runs_decreasing(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=50.0),
            _run(date(2024, 2, 29), risk_score=20.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "DECREASING"

    def test_trend_uses_only_last_three_runs_for_decrease(self):
        # First run has low score but only last 3 matter
        runs = [
            _run(date(2024, 1, 31), risk_score=0.0),  # outside trend window
            _run(date(2024, 2, 29), risk_score=70.0),
            _run(date(2024, 3, 31), risk_score=50.0),
            _run(date(2024, 4, 30), risk_score=20.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "DECREASING"

    def test_unsorted_input_still_detects_decreasing(self):
        runs = [
            _run(date(2024, 3, 31), risk_score=10.0),
            _run(date(2024, 1, 31), risk_score=80.0),
            _run(date(2024, 2, 29), risk_score=40.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "DECREASING"


# ---------------------------------------------------------------------------
# Single run edge case
# ---------------------------------------------------------------------------


class TestSingleRunEdgeCase:
    def test_single_run_trend_is_stable(self):
        runs = [_run(date(2024, 1, 31), risk_score=75.0)]
        result = analyze_client_risk_timeline(runs)
        assert result["risk_trend"] == "STABLE"

    def test_single_run_average_equals_its_score(self):
        runs = [_run(date(2024, 1, 31), risk_score=42.0)]
        result = analyze_client_risk_timeline(runs)
        assert result["average_risk_score"] == 42.0

    def test_single_run_counted_correctly(self):
        runs = [_run(date(2024, 1, 31), risk_score=10.0)]
        result = analyze_client_risk_timeline(runs)
        assert result["runs_analyzed"] == 1

    def test_single_high_risk_run_counted(self):
        runs = [_run(date(2024, 1, 31), risk_score=HIGH_RISK_THRESHOLD)]
        result = analyze_client_risk_timeline(runs)
        assert result["high_risk_runs"] == 1

    def test_single_below_threshold_run_not_high_risk(self):
        runs = [_run(date(2024, 1, 31), risk_score=HIGH_RISK_THRESHOLD - 0.01)]
        result = analyze_client_risk_timeline(runs)
        assert result["high_risk_runs"] == 0


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


class TestAggregateMetrics:
    def test_average_risk_score_computed_correctly(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=10.0),
            _run(date(2024, 2, 29), risk_score=30.0),
            _run(date(2024, 3, 31), risk_score=20.0),
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["average_risk_score"] == 20.0

    def test_runs_analyzed_counts_all_runs(self):
        runs = [_run(date(2024, i, 28), risk_score=float(i)) for i in range(1, 6)]
        result = analyze_client_risk_timeline(runs)
        assert result["runs_analyzed"] == 5

    def test_high_risk_runs_uses_threshold(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=10.0),   # not high risk
            _run(date(2024, 2, 29), risk_score=50.0),   # exactly at threshold → high
            _run(date(2024, 3, 31), risk_score=100.0),  # high risk
        ]
        result = analyze_client_risk_timeline(runs)
        assert result["high_risk_runs"] == 2

    def test_most_common_violations_ordered_by_frequency(self):
        runs = [
            _run(date(2024, 1, 31), findings=[
                _finding("RULE_A"), _finding("RULE_A"), _finding("RULE_B"),
            ]),
            _run(date(2024, 2, 29), findings=[
                _finding("RULE_A"), _finding("RULE_C"),
            ]),
        ]
        result = analyze_client_risk_timeline(runs)
        violations = result["most_common_violations"]
        # RULE_A appears 3x, RULE_B and RULE_C appear 1x each
        assert violations[0]["rule_id"] == "RULE_A"
        assert violations[0]["count"] == 3

    def test_most_common_violations_tie_broken_alphabetically(self):
        runs = [
            _run(date(2024, 1, 31), findings=[
                _finding("RULE_Z"), _finding("RULE_A"),
            ]),
        ]
        result = analyze_client_risk_timeline(runs)
        rule_ids = [v["rule_id"] for v in result["most_common_violations"]]
        # Both appear once — alphabetical tiebreak
        assert rule_ids == ["RULE_A", "RULE_Z"]

    def test_no_findings_produces_empty_violations(self):
        runs = [_run(date(2024, 1, 31), risk_score=5.0)]
        result = analyze_client_risk_timeline(runs)
        assert result["most_common_violations"] == []


# ---------------------------------------------------------------------------
# Deterministic output
# ---------------------------------------------------------------------------


class TestDeterministicOutput:
    def test_same_input_same_output(self):
        runs = [
            _run(date(2024, 1, 31), risk_score=10.0, findings=[_finding("RULE_A")]),
            _run(date(2024, 2, 29), risk_score=30.0, findings=[_finding("RULE_B")]),
            _run(date(2024, 3, 31), risk_score=60.0, findings=[_finding("RULE_A")]),
        ]
        first = analyze_client_risk_timeline(runs)
        second = analyze_client_risk_timeline(runs)
        third = analyze_client_risk_timeline(runs)
        assert first == second == third

    def test_input_order_does_not_affect_output(self):
        r1 = _run(date(2024, 1, 31), risk_score=10.0)
        r2 = _run(date(2024, 2, 29), risk_score=30.0)
        r3 = _run(date(2024, 3, 31), risk_score=60.0)

        result_asc = analyze_client_risk_timeline([r1, r2, r3])
        result_desc = analyze_client_risk_timeline([r3, r2, r1])
        result_mixed = analyze_client_risk_timeline([r2, r3, r1])

        assert result_asc == result_desc == result_mixed

    def test_output_always_contains_required_keys(self):
        required = {"risk_trend", "average_risk_score", "runs_analyzed", "high_risk_runs", "most_common_violations"}
        assert set(analyze_client_risk_timeline([])) == required
        assert set(analyze_client_risk_timeline([_run(date(2024, 1, 31))])) == required

    def test_risk_trend_always_one_of_three_values(self):
        for runs in [
            [],
            [_run(date(2024, 1, 31))],
            [_run(date(2024, 1, 31), risk_score=10), _run(date(2024, 2, 29), risk_score=20)],
        ]:
            assert analyze_client_risk_timeline(runs)["risk_trend"] in {"INCREASING", "DECREASING", "STABLE"}
