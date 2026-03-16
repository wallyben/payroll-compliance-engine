from __future__ import annotations

import pytest

from core.normalize.schema import CanonicalPayrollRow
from core.review.pre_submission_checks import run_pre_submission_checks

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_FINDING_KEYS = {
    "rule_id", "severity", "title", "description",
    "evidence", "suggestion", "amount_impact", "employee_refs",
}

VALID_PPSN = "1234567A"
VALID_PRSI_CLASS = "A"


def _row(
    employee_id: str,
    gross_pay: float = 3000.0,
    net_pay: float | None = None,
    hours: float | None = None,
    ppsn: str | None = VALID_PPSN,
    prsi_class: str | None = VALID_PRSI_CLASS,
) -> CanonicalPayrollRow:
    return CanonicalPayrollRow(
        employee_id=employee_id,
        gross_pay=gross_pay,
        net_pay=net_pay if net_pay is not None else gross_pay * 0.75,
        hours=hours,
        ppsn=ppsn,
        prsi_class=prsi_class,
    )


def _rule_ids(findings: list[dict]) -> list[str]:
    return [f["rule_id"] for f in findings]


def _finding_for(findings: list[dict], rule_id: str) -> dict:
    matches = [f for f in findings if f["rule_id"] == rule_id]
    assert matches, f"No finding with rule_id={rule_id!r} in {_rule_ids(findings)}"
    return matches[0]


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

class TestOutputContract:
    def test_returns_list(self):
        result = run_pre_submission_checks([], [])
        assert isinstance(result, list)

    def test_empty_payrolls_produce_no_findings(self):
        assert run_pre_submission_checks([], []) == []

    def test_clean_payroll_produces_no_findings(self):
        rows = [_row("E001"), _row("E002")]
        assert run_pre_submission_checks(rows, rows) == []

    def test_every_finding_has_required_keys(self):
        # Trigger multiple findings at once
        prev = [_row("E001")]
        curr = [_row("E002", ppsn=None, prsi_class=None)]
        findings = run_pre_submission_checks(prev, curr)
        for f in findings:
            assert set(f.keys()) >= _REQUIRED_FINDING_KEYS, (
                f"Finding {f['rule_id']} is missing keys: "
                f"{_REQUIRED_FINDING_KEYS - set(f.keys())}"
            )

    def test_finding_order_matches_rule_order(self):
        # All checks triggered simultaneously so order can be verified
        prev = [_row("E001", gross_pay=1000.0, hours=10.0, net_pay=800.0)]
        curr = [
            _row("E002", gross_pay=5000.0, hours=50.0, net_pay=-10.0, ppsn=None, prsi_class=None),
        ]
        findings = run_pre_submission_checks(prev, curr)
        ids = _rule_ids(findings)
        # Rule IDs should appear in their defined order (subset is fine)
        from core.review.pre_submission_checks import _RULE_ORDER
        order_indices = [_RULE_ORDER.index(rid) for rid in ids if rid in _RULE_ORDER]
        assert order_indices == sorted(order_indices), "Findings are not in _RULE_ORDER sequence"

    def test_employee_refs_are_sorted(self):
        prev = []
        curr = [_row("E003"), _row("E001"), _row("E002")]
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.POP.001")
        assert f["employee_refs"] == sorted(f["employee_refs"])


# ---------------------------------------------------------------------------
# QA.POP.001 – New employees
# ---------------------------------------------------------------------------

class TestNewEmployees:
    def test_new_employee_flagged(self):
        prev = [_row("E001")]
        curr = [_row("E001"), _row("E002")]
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.POP.001")
        assert f["severity"] == "LOW"
        assert "E002" in f["employee_refs"]
        assert f["evidence"]["count"] == 1

    def test_multiple_new_employees_all_referenced(self):
        prev = [_row("E001")]
        curr = [_row("E001"), _row("E002"), _row("E003")]
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.POP.001")
        assert set(f["employee_refs"]) == {"E002", "E003"}
        assert f["evidence"]["count"] == 2

    def test_no_new_employees_no_finding(self):
        rows = [_row("E001")]
        findings = run_pre_submission_checks(rows, rows)
        assert "QA.POP.001" not in _rule_ids(findings)

    def test_empty_previous_all_are_new(self):
        curr = [_row("E001"), _row("E002")]
        findings = run_pre_submission_checks([], curr)
        f = _finding_for(findings, "QA.POP.001")
        assert set(f["employee_refs"]) == {"E001", "E002"}


# ---------------------------------------------------------------------------
# QA.POP.002 – Removed employees
# ---------------------------------------------------------------------------

class TestRemovedEmployees:
    def test_removed_employee_flagged(self):
        prev = [_row("E001"), _row("E002")]
        curr = [_row("E001")]
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.POP.002")
        assert f["severity"] == "MEDIUM"
        assert "E002" in f["employee_refs"]

    def test_no_removed_employees_no_finding(self):
        rows = [_row("E001")]
        findings = run_pre_submission_checks(rows, rows)
        assert "QA.POP.002" not in _rule_ids(findings)


# ---------------------------------------------------------------------------
# QA.POP.003 – Duplicate employee IDs
# ---------------------------------------------------------------------------

class TestDuplicateEmployees:
    def test_duplicate_id_flagged(self):
        rows = [_row("E001"), _row("E001")]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.POP.003")
        assert f["severity"] == "HIGH"
        assert "E001" in f["employee_refs"]

    def test_unique_ids_no_finding(self):
        rows = [_row("E001"), _row("E002")]
        assert "QA.POP.003" not in _rule_ids(run_pre_submission_checks([], rows))

    def test_evidence_includes_counts(self):
        rows = [_row("E001"), _row("E001"), _row("E001")]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.POP.003")
        assert f["evidence"]["counts"]["E001"] == 3


# ---------------------------------------------------------------------------
# QA.SAL.001 – Salary spike > 20 %
# ---------------------------------------------------------------------------

class TestSalarySpike:
    def test_increase_above_20_pct_flagged(self):
        prev = [_row("E001", gross_pay=3000.0)]
        curr = [_row("E001", gross_pay=3700.0)]  # +23.3 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.SAL.001")
        assert f["severity"] == "MEDIUM"
        assert "E001" in f["employee_refs"]
        assert f["evidence"]["employees"]["E001"]["percent_change"] > 20.0

    def test_increase_exactly_20_pct_not_flagged(self):
        prev = [_row("E001", gross_pay=3000.0)]
        curr = [_row("E001", gross_pay=3600.0)]  # exactly 20 %
        assert "QA.SAL.001" not in _rule_ids(run_pre_submission_checks(prev, curr))

    def test_decrease_not_caught_by_sal001(self):
        prev = [_row("E001", gross_pay=3000.0)]
        curr = [_row("E001", gross_pay=2000.0)]
        assert "QA.SAL.001" not in _rule_ids(run_pre_submission_checks(prev, curr))

    def test_no_previous_no_sal001(self):
        # No comparison possible without previous
        curr = [_row("E001", gross_pay=9999.0)]
        assert "QA.SAL.001" not in _rule_ids(run_pre_submission_checks([], curr))


# ---------------------------------------------------------------------------
# QA.SAL.002 – Salary drop > 20 %
# ---------------------------------------------------------------------------

class TestSalaryDrop:
    def test_decrease_above_20_pct_flagged(self):
        prev = [_row("E001", gross_pay=3000.0)]
        curr = [_row("E001", gross_pay=2300.0)]  # -23.3 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.SAL.002")
        assert f["severity"] == "MEDIUM"
        assert f["evidence"]["employees"]["E001"]["percent_change"] < -20.0

    def test_decrease_exactly_20_pct_not_flagged(self):
        prev = [_row("E001", gross_pay=3000.0)]
        curr = [_row("E001", gross_pay=2400.0)]  # exactly -20 %
        assert "QA.SAL.002" not in _rule_ids(run_pre_submission_checks(prev, curr))


# ---------------------------------------------------------------------------
# QA.HRS.001 – Hours spike > 2×
# ---------------------------------------------------------------------------

class TestHoursSpike:
    def test_hours_more_than_double_flagged(self):
        prev = [_row("E001", hours=40.0)]
        curr = [_row("E001", hours=85.0)]  # > 2×
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.HRS.001")
        assert f["severity"] == "HIGH"
        assert "E001" in f["employee_refs"]
        assert f["evidence"]["employees"]["E001"]["factor"] > 2.0

    def test_hours_exactly_double_not_flagged(self):
        prev = [_row("E001", hours=40.0)]
        curr = [_row("E001", hours=80.0)]  # exactly 2×
        assert "QA.HRS.001" not in _rule_ids(run_pre_submission_checks(prev, curr))

    def test_missing_hours_not_flagged(self):
        prev = [_row("E001", hours=None)]
        curr = [_row("E001", hours=200.0)]
        assert "QA.HRS.001" not in _rule_ids(run_pre_submission_checks(prev, curr))


# ---------------------------------------------------------------------------
# QA.HRS.002 – Hours drop > 50 %
# ---------------------------------------------------------------------------

class TestHoursDrop:
    def test_hours_drop_above_50_pct_flagged(self):
        prev = [_row("E001", hours=40.0)]
        curr = [_row("E001", hours=18.0)]  # -55 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.HRS.002")
        assert f["severity"] == "MEDIUM"
        assert f["evidence"]["employees"]["E001"]["percent_drop"] > 50.0

    def test_hours_drop_exactly_50_pct_not_flagged(self):
        prev = [_row("E001", hours=40.0)]
        curr = [_row("E001", hours=20.0)]  # exactly 50 %
        assert "QA.HRS.002" not in _rule_ids(run_pre_submission_checks(prev, curr))


# ---------------------------------------------------------------------------
# QA.NET.001 – Negative net pay
# ---------------------------------------------------------------------------

class TestNegativeNetPay:
    def test_negative_net_pay_flagged(self):
        rows = [_row("E001", gross_pay=3000.0, net_pay=-50.0)]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.NET.001")
        assert f["severity"] == "HIGH"
        assert "E001" in f["employee_refs"]

    def test_zero_net_pay_not_flagged(self):
        rows = [_row("E001", gross_pay=3000.0, net_pay=0.0)]
        assert "QA.NET.001" not in _rule_ids(run_pre_submission_checks([], rows))

    def test_positive_net_pay_not_flagged(self):
        rows = [_row("E001")]
        assert "QA.NET.001" not in _rule_ids(run_pre_submission_checks([], rows))


# ---------------------------------------------------------------------------
# QA.NET.002 – Net > gross
# ---------------------------------------------------------------------------

class TestNetExceedsGross:
    def test_net_above_gross_flagged(self):
        rows = [_row("E001", gross_pay=3000.0, net_pay=3100.0)]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.NET.002")
        assert f["severity"] == "HIGH"
        assert "E001" in f["employee_refs"]

    def test_net_equal_to_gross_not_flagged(self):
        rows = [_row("E001", gross_pay=3000.0, net_pay=3000.0)]
        assert "QA.NET.002" not in _rule_ids(run_pre_submission_checks([], rows))

    def test_net_within_tolerance_not_flagged(self):
        # net == gross + 0.005 is within the 0.01 tolerance
        rows = [_row("E001", gross_pay=3000.0, net_pay=3000.005)]
        assert "QA.NET.002" not in _rule_ids(run_pre_submission_checks([], rows))


# ---------------------------------------------------------------------------
# QA.NET.003 – Net pay change > 30 %
# ---------------------------------------------------------------------------

class TestNetChange:
    def test_net_increase_above_30_pct_flagged(self):
        prev = [_row("E001", net_pay=2000.0)]
        curr = [_row("E001", net_pay=2700.0)]  # +35 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.NET.003")
        assert f["severity"] == "MEDIUM"
        assert f["evidence"]["employees"]["E001"]["percent_change"] > 30.0

    def test_net_decrease_above_30_pct_flagged(self):
        prev = [_row("E001", net_pay=2000.0)]
        curr = [_row("E001", net_pay=1300.0)]  # -35 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.NET.003")
        assert f["evidence"]["employees"]["E001"]["percent_change"] < -30.0

    def test_net_change_exactly_30_pct_not_flagged(self):
        prev = [_row("E001", net_pay=2000.0)]
        curr = [_row("E001", net_pay=2600.0)]  # exactly 30 %
        assert "QA.NET.003" not in _rule_ids(run_pre_submission_checks(prev, curr))


# ---------------------------------------------------------------------------
# QA.TOT.001 – Total payroll change > 15 %
# ---------------------------------------------------------------------------

class TestPayrollTotalJump:
    def test_total_increase_above_15_pct_flagged(self):
        prev = [_row("E001", gross_pay=5000.0), _row("E002", gross_pay=5000.0)]
        curr = [_row("E001", gross_pay=6000.0), _row("E002", gross_pay=6000.0)]  # +20 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.TOT.001")
        assert f["severity"] == "HIGH"
        assert f["evidence"]["percent_change"] > 15.0
        assert f["amount_impact"] is not None
        assert f["amount_impact"] > 0

    def test_total_decrease_above_15_pct_flagged(self):
        prev = [_row("E001", gross_pay=10000.0)]
        curr = [_row("E001", gross_pay=8000.0)]  # -20 %
        findings = run_pre_submission_checks(prev, curr)
        f = _finding_for(findings, "QA.TOT.001")
        assert f["evidence"]["percent_change"] < -15.0
        assert f["amount_impact"] == 2000.0

    def test_total_change_exactly_15_pct_not_flagged(self):
        prev = [_row("E001", gross_pay=10000.0)]
        curr = [_row("E001", gross_pay=11500.0)]  # exactly 15 %
        assert "QA.TOT.001" not in _rule_ids(run_pre_submission_checks(prev, curr))

    def test_no_previous_no_total_finding(self):
        curr = [_row("E001", gross_pay=99999.0)]
        assert "QA.TOT.001" not in _rule_ids(run_pre_submission_checks([], curr))


# ---------------------------------------------------------------------------
# QA.STAT.001 – Missing PPSN
# ---------------------------------------------------------------------------

class TestMissingPpsn:
    def test_missing_ppsn_flagged(self):
        rows = [_row("E001", ppsn=None)]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.STAT.001")
        assert f["severity"] == "MEDIUM"
        assert "E001" in f["employee_refs"]

    def test_empty_string_ppsn_flagged(self):
        rows = [_row("E001", ppsn="   ")]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.STAT.001")
        assert "E001" in f["employee_refs"]

    def test_present_ppsn_not_flagged_for_missing(self):
        rows = [_row("E001", ppsn=VALID_PPSN)]
        assert "QA.STAT.001" not in _rule_ids(run_pre_submission_checks([], rows))


# ---------------------------------------------------------------------------
# QA.STAT.002 – Invalid PPSN format
# ---------------------------------------------------------------------------

class TestInvalidPpsn:
    @pytest.mark.parametrize("bad_ppsn", [
        "123456",         # too short – only 6 digits
        "12345678A",      # 8 digits
        "ABCDEFGA",       # all letters
        "1234567",        # no letter
        "1234567AB1",     # trailing digit
        "123456 A",       # space inside
    ])
    def test_invalid_ppsn_format_flagged(self, bad_ppsn: str):
        rows = [_row("E001", ppsn=bad_ppsn)]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.STAT.002")
        assert f["severity"] == "HIGH"
        assert "E001" in f["employee_refs"]

    @pytest.mark.parametrize("good_ppsn", [
        "1234567A",   # standard single-letter suffix
        "1234567AB",  # two-letter suffix
        "0000001W",   # leading zero
    ])
    def test_valid_ppsn_not_flagged(self, good_ppsn: str):
        rows = [_row("E001", ppsn=good_ppsn)]
        assert "QA.STAT.002" not in _rule_ids(run_pre_submission_checks([], rows))

    def test_missing_ppsn_not_double_flagged_as_invalid(self):
        # A None PPSN is caught by QA.STAT.001 and must NOT also appear in QA.STAT.002
        rows = [_row("E001", ppsn=None)]
        findings = run_pre_submission_checks([], rows)
        if "QA.STAT.002" in _rule_ids(findings):
            f = _finding_for(findings, "QA.STAT.002")
            assert "E001" not in f["employee_refs"]

    def test_ppsn_case_insensitive(self):
        rows = [_row("E001", ppsn="1234567a")]  # lowercase letter
        assert "QA.STAT.002" not in _rule_ids(run_pre_submission_checks([], rows))


# ---------------------------------------------------------------------------
# QA.STAT.003 – Missing PRSI class
# ---------------------------------------------------------------------------

class TestMissingPrsiClass:
    def test_missing_prsi_class_flagged(self):
        rows = [_row("E001", prsi_class=None)]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.STAT.003")
        assert f["severity"] == "MEDIUM"
        assert "E001" in f["employee_refs"]

    def test_empty_string_prsi_class_flagged(self):
        rows = [_row("E001", prsi_class="  ")]
        findings = run_pre_submission_checks([], rows)
        f = _finding_for(findings, "QA.STAT.003")
        assert "E001" in f["employee_refs"]

    def test_present_prsi_class_not_flagged(self):
        rows = [_row("E001", prsi_class="A")]
        assert "QA.STAT.003" not in _rule_ids(run_pre_submission_checks([], rows))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_repeated_runs_identical_output(self):
        prev = [
            _row("E001", gross_pay=3000.0, hours=40.0, net_pay=2200.0),
            _row("E002", gross_pay=2000.0, hours=30.0, net_pay=1500.0),
        ]
        curr = [
            _row("E001", gross_pay=3700.0, hours=90.0, net_pay=2700.0),  # salary spike, hours spike
            _row("E003", gross_pay=1000.0, net_pay=-20.0, ppsn=None),    # new + neg net + missing PPSN
        ]
        first = run_pre_submission_checks(prev, curr)
        second = run_pre_submission_checks(prev, curr)
        third = run_pre_submission_checks(prev, curr)
        assert first == second == third

    def test_input_row_order_does_not_affect_output(self):
        prev_a = [_row("E001"), _row("E002")]
        prev_b = [_row("E002"), _row("E001")]
        curr_a = [_row("E001", gross_pay=4000.0), _row("E003")]
        curr_b = [_row("E003"), _row("E001", gross_pay=4000.0)]

        result_a = run_pre_submission_checks(prev_a, curr_a)
        result_b = run_pre_submission_checks(prev_b, curr_b)
        assert result_a == result_b

    def test_multiple_checks_fire_in_fixed_order(self):
        from core.review.pre_submission_checks import _RULE_ORDER

        prev = [_row("E001", gross_pay=3000.0, hours=40.0, net_pay=2000.0)]
        curr = [
            _row("E001", gross_pay=3700.0, hours=90.0, net_pay=2800.0),  # SAL.001, HRS.001, NET.003
            _row("E002", gross_pay=500.0, net_pay=-10.0, ppsn="BAD!", prsi_class=None),  # new, neg net, bad ppsn, no prsi
        ]
        findings = run_pre_submission_checks(prev, curr)
        ids = _rule_ids(findings)
        positions = [_RULE_ORDER.index(rid) for rid in ids if rid in _RULE_ORDER]
        assert positions == sorted(positions)
