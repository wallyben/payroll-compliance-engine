from __future__ import annotations

import pytest

from core.analysis.payroll_diff import compare_payrolls
from core.normalize.schema import CanonicalPayrollRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(employee_id: str, gross_pay: float, hours: float | None = None, name: str | None = None) -> CanonicalPayrollRow:
    return CanonicalPayrollRow(
        employee_id=employee_id,
        employee_name=name or f"Employee {employee_id}",
        gross_pay=gross_pay,
        net_pay=gross_pay * 0.8,
        hours=hours,
    )


# ---------------------------------------------------------------------------
# New employee detected
# ---------------------------------------------------------------------------

class TestNewEmployee:
    def test_single_new_employee_detected(self):
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 3000.0), _row("E002", 2500.0)]

        result = compare_payrolls(prev, curr)

        assert len(result["new_employees"]) == 1
        assert result["new_employees"][0]["employee_id"] == "E002"
        assert result["new_employees"][0]["gross_pay"] == 2500.0

    def test_multiple_new_employees_sorted(self):
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 3000.0), _row("E003", 1000.0), _row("E002", 2000.0)]

        result = compare_payrolls(prev, curr)

        ids = [e["employee_id"] for e in result["new_employees"]]
        assert ids == sorted(ids), "new_employees must be sorted by employee_id"
        assert ids == ["E002", "E003"]

    def test_no_false_positive_new_employees(self):
        prev = [_row("E001", 3000.0), _row("E002", 2500.0)]
        curr = [_row("E001", 3100.0), _row("E002", 2500.0)]

        result = compare_payrolls(prev, curr)

        assert result["new_employees"] == []

    def test_empty_previous_all_employees_are_new(self):
        curr = [_row("E001", 3000.0), _row("E002", 2000.0)]

        result = compare_payrolls([], curr)

        ids = [e["employee_id"] for e in result["new_employees"]]
        assert sorted(ids) == ["E001", "E002"]
        assert result["removed_employees"] == []


# ---------------------------------------------------------------------------
# Employee removed
# ---------------------------------------------------------------------------

class TestRemovedEmployee:
    def test_single_removed_employee_detected(self):
        prev = [_row("E001", 3000.0), _row("E002", 2500.0)]
        curr = [_row("E001", 3000.0)]

        result = compare_payrolls(prev, curr)

        assert len(result["removed_employees"]) == 1
        assert result["removed_employees"][0]["employee_id"] == "E002"
        assert result["removed_employees"][0]["gross_pay"] == 2500.0

    def test_multiple_removed_employees_sorted(self):
        prev = [_row("E001", 3000.0), _row("E002", 2000.0), _row("E003", 1000.0)]
        curr = [_row("E001", 3000.0)]

        result = compare_payrolls(prev, curr)

        ids = [e["employee_id"] for e in result["removed_employees"]]
        assert ids == sorted(ids), "removed_employees must be sorted by employee_id"
        assert ids == ["E002", "E003"]

    def test_no_false_positive_removed_employees(self):
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 3500.0)]

        result = compare_payrolls(prev, curr)

        assert result["removed_employees"] == []


# ---------------------------------------------------------------------------
# Salary change > 10 %
# ---------------------------------------------------------------------------

class TestSalaryChange:
    def test_salary_increase_above_threshold_detected(self):
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 3400.0)]  # +13.3 %

        result = compare_payrolls(prev, curr)

        assert len(result["salary_changes"]) == 1
        change = result["salary_changes"][0]
        assert change["employee_id"] == "E001"
        assert change["previous_gross_pay"] == 3000.0
        assert change["current_gross_pay"] == 3400.0
        assert change["percent_change"] > 10.0

    def test_salary_decrease_above_threshold_detected(self):
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 2600.0)]  # -13.3 %

        result = compare_payrolls(prev, curr)

        assert len(result["salary_changes"]) == 1
        assert result["salary_changes"][0]["percent_change"] < -10.0

    def test_salary_change_exactly_at_threshold_not_flagged(self):
        # Exactly 10 % is not *greater than* 10 %, so not flagged
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 3300.0)]  # exactly 10 %

        result = compare_payrolls(prev, curr)

        assert result["salary_changes"] == []

    def test_salary_change_below_threshold_not_flagged(self):
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 3250.0)]  # ~8.3 %

        result = compare_payrolls(prev, curr)

        assert result["salary_changes"] == []

    def test_salary_changes_sorted_by_employee_id(self):
        prev = [_row("E001", 3000.0), _row("E002", 2000.0), _row("E003", 1500.0)]
        curr = [_row("E001", 3400.0), _row("E002", 2300.0), _row("E003", 1700.0)]

        result = compare_payrolls(prev, curr)

        ids = [c["employee_id"] for c in result["salary_changes"]]
        assert ids == sorted(ids)
        assert set(ids) == {"E001", "E002", "E003"}


# ---------------------------------------------------------------------------
# Hours spike > 25 %
# ---------------------------------------------------------------------------

class TestHoursChange:
    def test_hours_spike_above_threshold_detected(self):
        prev = [_row("E001", 3000.0, hours=40.0)]
        curr = [_row("E001", 3000.0, hours=52.0)]  # +30 %

        result = compare_payrolls(prev, curr)

        assert len(result["hours_changes"]) == 1
        change = result["hours_changes"][0]
        assert change["employee_id"] == "E001"
        assert change["previous_hours"] == 40.0
        assert change["current_hours"] == 52.0
        assert change["percent_change"] > 25.0

    def test_hours_drop_above_threshold_detected(self):
        prev = [_row("E001", 3000.0, hours=40.0)]
        curr = [_row("E001", 3000.0, hours=28.0)]  # -30 %

        result = compare_payrolls(prev, curr)

        assert len(result["hours_changes"]) == 1
        assert result["hours_changes"][0]["percent_change"] < -25.0

    def test_hours_change_exactly_at_threshold_not_flagged(self):
        # Exactly 25 % is not *greater than* 25 %, so not flagged
        prev = [_row("E001", 3000.0, hours=40.0)]
        curr = [_row("E001", 3000.0, hours=50.0)]  # exactly 25 %

        result = compare_payrolls(prev, curr)

        assert result["hours_changes"] == []

    def test_hours_change_below_threshold_not_flagged(self):
        prev = [_row("E001", 3000.0, hours=40.0)]
        curr = [_row("E001", 3000.0, hours=48.0)]  # 20 %

        result = compare_payrolls(prev, curr)

        assert result["hours_changes"] == []

    def test_missing_hours_in_either_period_not_flagged(self):
        prev_no_hours = [_row("E001", 3000.0, hours=None)]
        curr_with_hours = [_row("E001", 3000.0, hours=80.0)]
        assert compare_payrolls(prev_no_hours, curr_with_hours)["hours_changes"] == []

        prev_with_hours = [_row("E001", 3000.0, hours=40.0)]
        curr_no_hours = [_row("E001", 3000.0, hours=None)]
        assert compare_payrolls(prev_with_hours, curr_no_hours)["hours_changes"] == []

    def test_hours_changes_sorted_by_employee_id(self):
        prev = [_row("E001", 3000.0, hours=40.0), _row("E002", 2000.0, hours=40.0)]
        curr = [_row("E001", 3000.0, hours=55.0), _row("E002", 2000.0, hours=55.0)]

        result = compare_payrolls(prev, curr)

        ids = [c["employee_id"] for c in result["hours_changes"]]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Payroll total change
# ---------------------------------------------------------------------------

class TestPayrollTotalChange:
    def test_total_change_computed_correctly(self):
        prev = [_row("E001", 3000.0), _row("E002", 2000.0)]
        curr = [_row("E001", 3300.0), _row("E002", 2200.0)]

        result = compare_payrolls(prev, curr)

        ptc = result["payroll_total_change"]
        assert ptc["previous_total"] == 5000.0
        assert ptc["current_total"] == 5500.0
        assert ptc["absolute_change"] == 500.0
        assert ptc["percent_change"] == 10.0

    def test_total_change_with_empty_previous(self):
        curr = [_row("E001", 3000.0)]

        result = compare_payrolls([], curr)

        ptc = result["payroll_total_change"]
        assert ptc["previous_total"] == 0.0
        assert ptc["current_total"] == 3000.0
        assert ptc["absolute_change"] == 3000.0
        assert ptc["percent_change"] is None  # no previous baseline

    def test_total_decrease_has_negative_change(self):
        prev = [_row("E001", 5000.0)]
        curr = [_row("E001", 4000.0)]

        result = compare_payrolls(prev, curr)

        ptc = result["payroll_total_change"]
        assert ptc["absolute_change"] == -1000.0
        assert ptc["percent_change"] == -20.0


# ---------------------------------------------------------------------------
# No changes
# ---------------------------------------------------------------------------

class TestNoChanges:
    def test_identical_payrolls_produce_empty_changes(self):
        rows = [_row("E001", 3000.0, hours=40.0), _row("E002", 2500.0, hours=37.5)]

        result = compare_payrolls(rows, rows)

        assert result["new_employees"] == []
        assert result["removed_employees"] == []
        assert result["salary_changes"] == []
        assert result["hours_changes"] == []
        ptc = result["payroll_total_change"]
        assert ptc["absolute_change"] == 0.0
        assert ptc["percent_change"] == 0.0

    def test_sub_threshold_changes_all_suppressed(self):
        prev = [_row("E001", 3000.0, hours=40.0)]
        curr = [_row("E001", 3200.0, hours=48.0)]  # salary +6.7 %, hours +20 %

        result = compare_payrolls(prev, curr)

        assert result["salary_changes"] == []
        assert result["hours_changes"] == []


# ---------------------------------------------------------------------------
# Determinism – repeated runs produce identical output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output_repeated_calls(self):
        prev = [
            _row("E003", 1500.0, hours=30.0),
            _row("E001", 3000.0, hours=40.0),
            _row("E002", 2000.0, hours=20.0),
        ]
        curr = [
            _row("E001", 3400.0, hours=55.0),  # salary spike + hours spike
            _row("E004", 1200.0),               # new employee
            _row("E002", 2000.0, hours=20.0),  # unchanged
            # E003 removed
        ]

        first = compare_payrolls(prev, curr)
        second = compare_payrolls(prev, curr)
        third = compare_payrolls(prev, curr)

        assert first == second == third

    def test_output_order_is_stable_regardless_of_input_order(self):
        prev_a = [_row("E001", 3000.0), _row("E002", 2000.0)]
        prev_b = [_row("E002", 2000.0), _row("E001", 3000.0)]  # reversed

        curr = [_row("E001", 3400.0), _row("E003", 1000.0)]  # E002 removed, E003 added

        result_a = compare_payrolls(prev_a, curr)
        result_b = compare_payrolls(prev_b, curr)

        assert result_a == result_b

    def test_output_keys_always_present(self):
        result = compare_payrolls([], [])

        expected_keys = {"new_employees", "removed_employees", "salary_changes", "hours_changes", "payroll_total_change"}
        assert set(result.keys()) == expected_keys

    def test_payroll_total_change_keys_always_present(self):
        result = compare_payrolls([], [])

        expected_keys = {"previous_total", "current_total", "absolute_change", "percent_change"}
        assert set(result["payroll_total_change"].keys()) == expected_keys


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_both_empty(self):
        result = compare_payrolls([], [])

        assert result["new_employees"] == []
        assert result["removed_employees"] == []
        assert result["salary_changes"] == []
        assert result["hours_changes"] == []
        ptc = result["payroll_total_change"]
        assert ptc["previous_total"] == 0.0
        assert ptc["current_total"] == 0.0
        assert ptc["absolute_change"] == 0.0
        assert ptc["percent_change"] is None

    def test_zero_previous_gross_pay_no_salary_change_flagged(self):
        # Avoid division-by-zero: if previous gross_pay == 0.0 skip salary check
        prev = [_row("E001", 0.0)]
        curr = [_row("E001", 3000.0)]

        result = compare_payrolls(prev, curr)

        assert result["salary_changes"] == []

    def test_employee_name_carried_through(self):
        prev = [_row("E001", 3000.0, name="Alice")]
        curr = [_row("E002", 2000.0, name="Bob")]

        result = compare_payrolls(prev, curr)

        assert result["new_employees"][0]["employee_name"] == "Bob"
        assert result["removed_employees"][0]["employee_name"] == "Alice"

    def test_percent_change_rounded_to_4_decimal_places(self):
        # 1/3 = 33.333... % — verify rounding applied
        prev = [_row("E001", 3000.0)]
        curr = [_row("E001", 4000.0)]  # +33.333...%

        result = compare_payrolls(prev, curr)

        pct = result["salary_changes"][0]["percent_change"]
        assert pct == round(pct, 4)
        assert str(pct).count(".") <= 1  # is a plain number, not a string
