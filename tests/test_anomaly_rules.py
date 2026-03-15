"""Tests for core/rules/anomaly_rules.py.

Each test is self-contained and uses only CanonicalPayrollRow objects with
explicit field values so that outputs are fully deterministic.
"""
from __future__ import annotations

import pytest

from core.normalize.schema import CanonicalPayrollRow
from core.rules.anomaly_rules import (
    ANOMALY_RULE_ORDER,
    ANOMALY_005_FALLBACK_THRESHOLD,
    GROSS_DECREASE_THRESHOLD,
    GROSS_INCREASE_THRESHOLD,
    HOURS_INCREASE_MULTIPLIER,
    NEW_EMP_HIGH_PAY_MULTIPLIER,
    rule_anomaly_001_gross_pay_increase,
    rule_anomaly_002_gross_pay_decrease,
    rule_anomaly_003_hours_increase,
    rule_anomaly_004_negative_net_pay,
    rule_anomaly_005_new_employee_high_pay,
    run_anomaly_checks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(employee_id: str, gross_pay: float, net_pay: float = None, hours: float = None) -> CanonicalPayrollRow:
    if net_pay is None:
        net_pay = gross_pay * 0.75  # sensible default
    kw = {"employee_id": employee_id, "gross_pay": gross_pay, "net_pay": net_pay}
    if hours is not None:
        kw["hours"] = hours
    return CanonicalPayrollRow(**kw)


REQUIRED_FINDING_KEYS = frozenset({
    "rule_id", "severity", "title", "description",
    "evidence", "suggestion", "amount_impact", "employee_refs",
})


def _assert_finding_shape(finding: dict, expected_rule_id: str) -> None:
    assert set(finding.keys()) >= REQUIRED_FINDING_KEYS, "Finding is missing required keys"
    assert finding["rule_id"] == expected_rule_id
    assert finding["severity"] == "MEDIUM"
    assert isinstance(finding["employee_refs"], list)
    assert isinstance(finding["evidence"], dict)


# ===========================================================================
# ANOMALY.001 — gross pay increase > 50 %
# ===========================================================================

class TestAnomaly001GrossPayIncrease:

    def test_no_findings_on_normal_increase(self):
        """A 30 % increase is below the 50 % threshold — no finding expected."""
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 2600.0)]  # +30 %
        assert rule_anomaly_001_gross_pay_increase(curr, prev) == []

    def test_flags_large_increase(self):
        """A 60 % increase exceeds the threshold and must be flagged."""
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 3200.0)]  # +60 %
        findings = rule_anomaly_001_gross_pay_increase(curr, prev)
        assert len(findings) == 1
        _assert_finding_shape(findings[0], "IE.ANOMALY.001")
        assert "E1" in findings[0]["employee_refs"]
        assert findings[0]["evidence"]["count"] == 1

    def test_exact_threshold_not_flagged(self):
        """Exactly 50 % increase is at the boundary — not strictly greater, so no flag."""
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 3000.0)]  # exactly +50 %
        assert rule_anomaly_001_gross_pay_increase(curr, prev) == []

    def test_multiple_employees_only_large_flagged(self):
        prev = [_row("E1", 1000.0), _row("E2", 1000.0)]
        curr = [_row("E1", 1400.0), _row("E2", 2000.0)]  # E1 +40 %, E2 +100 %
        findings = rule_anomaly_001_gross_pay_increase(curr, prev)
        assert len(findings) == 1
        assert findings[0]["employee_refs"] == ["E2"]

    def test_new_employee_skipped(self):
        """An employee absent from the previous period has no baseline — should not flag."""
        prev: list = []
        curr = [_row("NEW", 5000.0)]
        assert rule_anomaly_001_gross_pay_increase(curr, prev) == []

    def test_employee_refs_capped_at_200(self):
        prev = [_row(f"E{i}", 1000.0) for i in range(250)]
        curr = [_row(f"E{i}", 3000.0) for i in range(250)]  # all +200 %
        findings = rule_anomaly_001_gross_pay_increase(curr, prev)
        assert len(findings) == 1
        assert len(findings[0]["employee_refs"]) == 200

    def test_deterministic_output(self):
        """Same inputs must produce identical outputs on repeated calls."""
        prev = [_row("E1", 1000.0), _row("E2", 500.0)]
        curr = [_row("E1", 2000.0), _row("E2", 900.0)]
        r1 = rule_anomaly_001_gross_pay_increase(curr, prev)
        r2 = rule_anomaly_001_gross_pay_increase(curr, prev)
        assert r1 == r2

    def test_evidence_max_increase_pct(self):
        prev = [_row("E1", 1000.0), _row("E2", 1000.0)]
        curr = [_row("E1", 2500.0), _row("E2", 2000.0)]  # E1 +150 %, E2 +100 %
        findings = rule_anomaly_001_gross_pay_increase(curr, prev)
        assert findings[0]["evidence"]["max_increase_pct"] == pytest.approx(1.5)


# ===========================================================================
# ANOMALY.002 — gross pay decrease > 40 %
# ===========================================================================

class TestAnomaly002GrossPayDecrease:

    def test_no_findings_on_normal_decrease(self):
        """A 25 % decrease is below the 40 % threshold — no finding expected."""
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 1500.0)]  # -25 %
        assert rule_anomaly_002_gross_pay_decrease(curr, prev) == []

    def test_flags_large_decrease(self):
        """A 50 % decrease exceeds the threshold and must be flagged."""
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 1000.0)]  # -50 %
        findings = rule_anomaly_002_gross_pay_decrease(curr, prev)
        assert len(findings) == 1
        _assert_finding_shape(findings[0], "IE.ANOMALY.002")
        assert "E1" in findings[0]["employee_refs"]

    def test_exact_threshold_not_flagged(self):
        """Exactly 40 % decrease at the boundary — no flag."""
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 1200.0)]  # exactly -40 %
        assert rule_anomaly_002_gross_pay_decrease(curr, prev) == []

    def test_multiple_employees_only_large_flagged(self):
        prev = [_row("E1", 2000.0), _row("E2", 2000.0)]
        curr = [_row("E1", 1600.0), _row("E2", 800.0)]  # E1 -20 %, E2 -60 %
        findings = rule_anomaly_002_gross_pay_decrease(curr, prev)
        assert len(findings) == 1
        assert findings[0]["employee_refs"] == ["E2"]

    def test_evidence_max_decrease_pct(self):
        prev = [_row("E1", 1000.0)]
        curr = [_row("E1", 400.0)]  # -60 %
        findings = rule_anomaly_002_gross_pay_decrease(curr, prev)
        assert findings[0]["evidence"]["max_decrease_pct"] == pytest.approx(0.6)

    def test_deterministic_output(self):
        prev = [_row("E1", 3000.0)]
        curr = [_row("E1", 1000.0)]
        assert rule_anomaly_002_gross_pay_decrease(curr, prev) == rule_anomaly_002_gross_pay_decrease(curr, prev)


# ===========================================================================
# ANOMALY.003 — hours worked increase > 2×
# ===========================================================================

class TestAnomaly003HoursIncrease:

    def test_no_findings_on_normal_hours(self):
        prev = [_row("E1", 2000.0, hours=40.0)]
        curr = [_row("E1", 2000.0, hours=50.0)]  # 1.25×
        assert rule_anomaly_003_hours_increase(curr, prev) == []

    def test_flags_extreme_hours(self):
        """Hours that more than doubled must be flagged."""
        prev = [_row("E1", 2000.0, hours=40.0)]
        curr = [_row("E1", 2000.0, hours=100.0)]  # 2.5×
        findings = rule_anomaly_003_hours_increase(curr, prev)
        assert len(findings) == 1
        _assert_finding_shape(findings[0], "IE.ANOMALY.003")
        assert "E1" in findings[0]["employee_refs"]

    def test_exact_multiplier_not_flagged(self):
        """Exactly 2× is at the boundary — not strictly greater, so no flag."""
        prev = [_row("E1", 2000.0, hours=40.0)]
        curr = [_row("E1", 2000.0, hours=80.0)]  # exactly 2×
        assert rule_anomaly_003_hours_increase(curr, prev) == []

    def test_skipped_when_hours_missing(self):
        """Rows without hours data should be silently skipped."""
        prev = [_row("E1", 2000.0)]       # hours=None
        curr = [_row("E1", 2000.0)]       # hours=None
        assert rule_anomaly_003_hours_increase(curr, prev) == []

    def test_skipped_when_previous_hours_missing(self):
        prev = [_row("E1", 2000.0)]       # hours=None
        curr = [_row("E1", 2000.0, hours=100.0)]
        assert rule_anomaly_003_hours_increase(curr, prev) == []

    def test_evidence_max_ratio(self):
        prev = [_row("E1", 2000.0, hours=20.0)]
        curr = [_row("E1", 2000.0, hours=100.0)]  # ratio = 5.0
        findings = rule_anomaly_003_hours_increase(curr, prev)
        assert findings[0]["evidence"]["max_ratio"] == pytest.approx(5.0)

    def test_deterministic_output(self):
        prev = [_row("E1", 2000.0, hours=30.0)]
        curr = [_row("E1", 2000.0, hours=90.0)]
        assert rule_anomaly_003_hours_increase(curr, prev) == rule_anomaly_003_hours_increase(curr, prev)


# ===========================================================================
# ANOMALY.004 — negative net pay
# ===========================================================================

class TestAnomaly004NegativeNetPay:

    def test_no_findings_on_positive_net(self):
        curr = [_row("E1", 2000.0, net_pay=1500.0)]
        assert rule_anomaly_004_negative_net_pay(curr, []) == []

    def test_flags_negative_net(self):
        curr = [_row("E1", 2000.0, net_pay=-50.0)]
        findings = rule_anomaly_004_negative_net_pay(curr, [])
        assert len(findings) == 1
        _assert_finding_shape(findings[0], "IE.ANOMALY.004")
        assert "E1" in findings[0]["employee_refs"]

    def test_zero_net_not_flagged(self):
        """Zero is not negative — should not produce a finding."""
        curr = [_row("E1", 2000.0, net_pay=0.0)]
        assert rule_anomaly_004_negative_net_pay(curr, []) == []

    def test_previous_payroll_not_used(self):
        """Previous payroll is ignored for this rule — passing empty list is fine."""
        curr = [_row("E1", 2000.0, net_pay=-100.0)]
        assert rule_anomaly_004_negative_net_pay(curr, []) == rule_anomaly_004_negative_net_pay(curr, [_row("E2", 999.0)])

    def test_multiple_negative_employees(self):
        curr = [
            _row("E1", 2000.0, net_pay=-10.0),
            _row("E2", 1500.0, net_pay=900.0),
            _row("E3", 1000.0, net_pay=-5.0),
        ]
        findings = rule_anomaly_004_negative_net_pay(curr, [])
        assert len(findings) == 1
        assert findings[0]["evidence"]["count"] == 2
        assert set(findings[0]["employee_refs"]) == {"E1", "E3"}

    def test_amount_impact_is_abs_min_net(self):
        curr = [_row("E1", 2000.0, net_pay=-200.0), _row("E2", 2000.0, net_pay=-50.0)]
        findings = rule_anomaly_004_negative_net_pay(curr, [])
        assert findings[0]["amount_impact"] == pytest.approx(200.0)

    def test_deterministic_output(self):
        curr = [_row("E1", 2000.0, net_pay=-75.0)]
        assert rule_anomaly_004_negative_net_pay(curr, []) == rule_anomaly_004_negative_net_pay(curr, [])


# ===========================================================================
# ANOMALY.005 — unusually high pay for new employee
# ===========================================================================

class TestAnomaly005NewEmployeeHighPay:

    def test_no_findings_when_no_new_employees(self):
        prev = [_row("E1", 2000.0), _row("E2", 2000.0)]
        curr = [_row("E1", 2000.0), _row("E2", 2000.0)]
        assert rule_anomaly_005_new_employee_high_pay(curr, prev) == []

    def test_no_findings_when_new_employee_pay_is_normal(self):
        """New employee whose pay is below 2× mean — no finding."""
        prev = [_row("E1", 2000.0), _row("E2", 2000.0)]  # mean = 2000
        curr = [_row("E1", 2000.0), _row("NEW", 3000.0)]  # NEW gross < 2×2000=4000
        assert rule_anomaly_005_new_employee_high_pay(curr, prev) == []

    def test_flags_new_high_pay_employee(self):
        """New employee whose pay exceeds 2× mean of previous employees."""
        prev = [_row("E1", 2000.0), _row("E2", 2000.0)]  # mean = 2000
        curr = [_row("E1", 2000.0), _row("NEW", 5000.0)]  # 5000 > 2×2000=4000
        findings = rule_anomaly_005_new_employee_high_pay(curr, prev)
        assert len(findings) == 1
        _assert_finding_shape(findings[0], "IE.ANOMALY.005")
        assert "NEW" in findings[0]["employee_refs"]

    def test_fallback_threshold_used_when_no_previous(self):
        """With no previous data, ANOMALY_005_FALLBACK_THRESHOLD is used."""
        curr = [_row("NEW", ANOMALY_005_FALLBACK_THRESHOLD + 1.0)]
        findings = rule_anomaly_005_new_employee_high_pay(curr, [])
        assert len(findings) == 1
        assert findings[0]["evidence"]["threshold"] == pytest.approx(ANOMALY_005_FALLBACK_THRESHOLD)

    def test_fallback_threshold_exact_not_flagged(self):
        curr = [_row("NEW", ANOMALY_005_FALLBACK_THRESHOLD)]
        assert rule_anomaly_005_new_employee_high_pay(curr, []) == []

    def test_existing_employee_not_flagged_as_new(self):
        prev = [_row("E1", 1000.0)]
        curr = [_row("E1", 99000.0)]  # huge increase but not a new employee
        assert rule_anomaly_005_new_employee_high_pay(curr, prev) == []

    def test_evidence_contains_threshold_and_mean(self):
        prev = [_row("E1", 3000.0), _row("E2", 1000.0)]  # mean = 2000
        curr = [_row("E1", 3000.0), _row("NEW", 5000.0)]
        findings = rule_anomaly_005_new_employee_high_pay(curr, prev)
        ev = findings[0]["evidence"]
        assert ev["mean_prev_gross"] == pytest.approx(2000.0)
        assert ev["threshold"] == pytest.approx(4000.0)
        assert ev["max_new_employee_gross"] == pytest.approx(5000.0)

    def test_deterministic_output(self):
        prev = [_row("E1", 2000.0)]
        curr = [_row("E1", 2000.0), _row("NEW", 9000.0)]
        assert rule_anomaly_005_new_employee_high_pay(curr, prev) == rule_anomaly_005_new_employee_high_pay(curr, prev)


# ===========================================================================
# run_anomaly_checks — combined runner
# ===========================================================================

class TestRunAnomalyChecks:

    def test_returns_no_findings_for_normal_payroll(self):
        prev = [_row("E1", 2000.0, hours=40.0), _row("E2", 1800.0, hours=37.5)]
        curr = [_row("E1", 2100.0, hours=42.0), _row("E2", 1900.0, hours=38.0)]
        findings = run_anomaly_checks(curr, prev)
        assert findings == []

    def test_returns_findings_for_combined_anomalies(self):
        """Run all anomalies at once and confirm the correct rule IDs are present."""
        prev = [_row("E1", 2000.0, hours=40.0)]
        curr = [
            _row("E1", 4000.0, hours=120.0),  # +100 % gross (ANOMALY.001), 3× hours (ANOMALY.003)
            _row("NEW", 50000.0, net_pay=-100.0),  # new high-pay (ANOMALY.005), negative net (ANOMALY.004)
        ]
        findings = run_anomaly_checks(curr, prev)
        rule_ids = {f["rule_id"] for f in findings}
        assert "IE.ANOMALY.001" in rule_ids
        assert "IE.ANOMALY.003" in rule_ids
        assert "IE.ANOMALY.004" in rule_ids
        assert "IE.ANOMALY.005" in rule_ids

    def test_run_order_matches_anomaly_rule_order(self):
        """Findings must be emitted in ANOMALY_RULE_ORDER sequence."""
        prev = [_row("E1", 2000.0, hours=40.0)]
        curr = [
            _row("E1", 4000.0, hours=120.0),   # triggers 001, 003
            _row("E2", 500.0),                  # triggers 002 (prev E2 not present → skipped)
            _row("NEW", -50.0, net_pay=-50.0),  # triggers 004, 005 (negative gross skipped by schema — use valid gross)
        ]
        # Use a valid gross for NEW
        curr = [
            _row("E1", 4000.0, hours=120.0),
            _row("NEW", 50000.0, net_pay=-50.0),
        ]
        findings = run_anomaly_checks(curr, prev)
        emitted_ids = [f["rule_id"] for f in findings]
        # Must appear in the order defined by ANOMALY_RULE_ORDER
        order_map = {rid: i for i, rid in enumerate(
            ["IE.ANOMALY.001", "IE.ANOMALY.002", "IE.ANOMALY.003", "IE.ANOMALY.004", "IE.ANOMALY.005"]
        )}
        indices = [order_map[rid] for rid in emitted_ids if rid in order_map]
        assert indices == sorted(indices), "Findings must be emitted in canonical rule order"

    def test_deterministic_on_repeated_calls(self):
        prev = [_row("E1", 1000.0, hours=20.0)]
        curr = [_row("E1", 3000.0, hours=80.0), _row("NEW", 25000.0, net_pay=-5.0)]
        r1 = run_anomaly_checks(curr, prev)
        r2 = run_anomaly_checks(curr, prev)
        assert r1 == r2

    def test_all_findings_have_required_keys(self):
        prev = [_row("E1", 1000.0, hours=20.0)]
        curr = [_row("E1", 3000.0, hours=80.0), _row("NEW", 25000.0, net_pay=-5.0)]
        for finding in run_anomaly_checks(curr, prev):
            assert set(finding.keys()) >= REQUIRED_FINDING_KEYS

    def test_all_findings_are_medium_severity(self):
        prev = [_row("E1", 1000.0, hours=20.0)]
        curr = [_row("E1", 3000.0, hours=80.0), _row("NEW", 25000.0, net_pay=-5.0)]
        for finding in run_anomaly_checks(curr, prev):
            assert finding["severity"] == "MEDIUM"


# ===========================================================================
# Module-level constant sanity checks
# ===========================================================================

class TestConstants:

    def test_anomaly_rule_order_length(self):
        assert len(ANOMALY_RULE_ORDER) == 5

    def test_anomaly_rule_order_contents(self):
        assert "rule_anomaly_001_gross_pay_increase" in ANOMALY_RULE_ORDER
        assert "rule_anomaly_002_gross_pay_decrease" in ANOMALY_RULE_ORDER
        assert "rule_anomaly_003_hours_increase" in ANOMALY_RULE_ORDER
        assert "rule_anomaly_004_negative_net_pay" in ANOMALY_RULE_ORDER
        assert "rule_anomaly_005_new_employee_high_pay" in ANOMALY_RULE_ORDER

    def test_threshold_values_are_positive(self):
        assert GROSS_INCREASE_THRESHOLD > 0
        assert GROSS_DECREASE_THRESHOLD > 0
        assert HOURS_INCREASE_MULTIPLIER > 1
        assert NEW_EMP_HIGH_PAY_MULTIPLIER > 1
        assert ANOMALY_005_FALLBACK_THRESHOLD > 0
