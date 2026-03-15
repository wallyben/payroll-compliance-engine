from __future__ import annotations

from typing import List

from core.normalize.schema import CanonicalPayrollRow

# Detection thresholds
_SALARY_CHANGE_THRESHOLD = 0.10  # flag changes > 10%
_HOURS_CHANGE_THRESHOLD = 0.25   # flag changes > 25%


def compare_payrolls(
    previous_rows: List[CanonicalPayrollRow],
    current_rows: List[CanonicalPayrollRow],
) -> dict:
    """Compare current payroll dataset against previous payroll dataset.

    Employee matching is done via ``employee_id``.  All output lists are
    sorted by ``employee_id`` for deterministic, stable ordering.

    When *previous_rows* is empty (first-run / no prior payroll) every
    current employee is returned as a new employee and totals are computed
    against a zero baseline.

    Returns
    -------
    dict with keys:
        new_employees       – employees present in current but not previous
        removed_employees   – employees present in previous but not current
        salary_changes      – gross_pay change > 10 % for matched employees
        hours_changes       – hours change > 25 % for matched employees
        payroll_total_change – aggregate payroll movement
    """
    curr_by_id: dict[str, CanonicalPayrollRow] = {r.employee_id: r for r in current_rows}
    prev_by_id: dict[str, CanonicalPayrollRow] = {r.employee_id: r for r in previous_rows}

    prev_ids = set(prev_by_id)
    curr_ids = set(curr_by_id)

    # ── New employees ────────────────────────────────────────────────────────
    new_employees = sorted(
        [
            {
                "employee_id": eid,
                "employee_name": curr_by_id[eid].employee_name,
                "gross_pay": curr_by_id[eid].gross_pay,
            }
            for eid in (curr_ids - prev_ids)
        ],
        key=lambda x: x["employee_id"],
    )

    # ── Removed employees ────────────────────────────────────────────────────
    removed_employees = sorted(
        [
            {
                "employee_id": eid,
                "employee_name": prev_by_id[eid].employee_name,
                "gross_pay": prev_by_id[eid].gross_pay,
            }
            for eid in (prev_ids - curr_ids)
        ],
        key=lambda x: x["employee_id"],
    )

    # ── Per-employee change detection ────────────────────────────────────────
    salary_changes: list[dict] = []
    hours_changes: list[dict] = []

    for eid in sorted(prev_ids & curr_ids):
        prev = prev_by_id[eid]
        curr = curr_by_id[eid]

        # Salary change > 10 %
        if prev.gross_pay != 0.0:
            salary_pct = (curr.gross_pay - prev.gross_pay) / abs(prev.gross_pay)
            if abs(salary_pct) > _SALARY_CHANGE_THRESHOLD:
                salary_changes.append(
                    {
                        "employee_id": eid,
                        "employee_name": curr.employee_name,
                        "previous_gross_pay": prev.gross_pay,
                        "current_gross_pay": curr.gross_pay,
                        "percent_change": round(salary_pct * 100, 4),
                    }
                )

        # Hours change > 25 %
        if prev.hours is not None and curr.hours is not None and prev.hours != 0.0:
            hours_pct = (curr.hours - prev.hours) / abs(prev.hours)
            if abs(hours_pct) > _HOURS_CHANGE_THRESHOLD:
                hours_changes.append(
                    {
                        "employee_id": eid,
                        "employee_name": curr.employee_name,
                        "previous_hours": prev.hours,
                        "current_hours": curr.hours,
                        "percent_change": round(hours_pct * 100, 4),
                    }
                )

    # ── Total payroll change ─────────────────────────────────────────────────
    previous_total = sum(r.gross_pay for r in previous_rows)
    current_total = sum(r.gross_pay for r in current_rows)
    absolute_change = current_total - previous_total
    percent_change = (
        round(absolute_change / abs(previous_total) * 100, 4)
        if previous_total != 0.0
        else None
    )

    payroll_total_change = {
        "previous_total": round(previous_total, 2),
        "current_total": round(current_total, 2),
        "absolute_change": round(absolute_change, 2),
        "percent_change": percent_change,
    }

    return {
        "new_employees": new_employees,
        "removed_employees": removed_employees,
        "salary_changes": salary_changes,
        "hours_changes": hours_changes,
        "payroll_total_change": payroll_total_change,
    }
