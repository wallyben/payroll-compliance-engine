"""Payroll anomaly detection rules.

These rules compare current payroll against a previous payroll snapshot to
surface unusual changes.  They produce MEDIUM-severity warnings rather than
compliance violations, so they are intentionally kept separate from the
statutory rules in rules.py.

Rule IDs follow the convention IE.ANOMALY.NNN.

Public API
----------
Each rule function has the signature::

    rule_anomaly_NNN_*(
        current: List[CanonicalPayrollRow],
        previous: List[CanonicalPayrollRow],
    ) -> List[dict]

All returned dicts are compatible with the rule-engine finding format
(same keys as REQUIRED_FINDING_KEYS in core/rules/engine.py).

run_anomaly_checks(current, previous) -> List[dict]
    Convenience wrapper that runs all five rules in a deterministic order.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core.normalize.schema import CanonicalPayrollRow

# ---------------------------------------------------------------------------
# Thresholds (module-level constants for determinism and easy testing)
# ---------------------------------------------------------------------------
GROSS_INCREASE_THRESHOLD = 0.50   # ANOMALY.001 — flag if gross rises > 50 %
GROSS_DECREASE_THRESHOLD = 0.40   # ANOMALY.002 — flag if gross falls > 40 %
HOURS_INCREASE_MULTIPLIER = 2.0   # ANOMALY.003 — flag if hours more than double
# ANOMALY.005: flag new employees whose gross exceeds this multiple of the
# previous-period mean.  Falls back to ANOMALY_005_FALLBACK_THRESHOLD when
# there is no previous payroll to derive a mean from.
NEW_EMP_HIGH_PAY_MULTIPLIER = 2.0
ANOMALY_005_FALLBACK_THRESHOLD = 10_000.0  # euros — used when no prior data

# Canonical execution order exposed for external callers / tests.
ANOMALY_RULE_ORDER: tuple[str, ...] = (
    "rule_anomaly_001_gross_pay_increase",
    "rule_anomaly_002_gross_pay_decrease",
    "rule_anomaly_003_hours_increase",
    "rule_anomaly_004_negative_net_pay",
    "rule_anomaly_005_new_employee_high_pay",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _finding(rule_id: str, severity: str, title: str, description: str, **kw) -> dict:
    """Build a finding dict that satisfies REQUIRED_FINDING_KEYS."""
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        "description": description,
        "evidence": kw.get("evidence", {}),
        "suggestion": kw.get("suggestion", ""),
        "amount_impact": kw.get("amount_impact"),
        "employee_refs": kw.get("employee_refs", []),
    }


def _index_by_employee(rows: List[CanonicalPayrollRow]) -> Dict[str, CanonicalPayrollRow]:
    """Return a dict keyed by employee_id (last occurrence wins on duplicates)."""
    return {r.employee_id: r for r in rows}


# ---------------------------------------------------------------------------
# ANOMALY.001 — gross pay increase > 50 %
# ---------------------------------------------------------------------------

def rule_anomaly_001_gross_pay_increase(
    current: List[CanonicalPayrollRow],
    previous: List[CanonicalPayrollRow],
) -> List[dict]:
    """Flag employees whose gross pay increased by more than 50 % vs the prior period."""
    prev_idx = _index_by_employee(previous)
    flagged: List[str] = []
    max_pct: Optional[float] = None

    for row in current:
        prev = prev_idx.get(row.employee_id)
        if prev is None or prev.gross_pay <= 0:
            continue
        pct_change = (row.gross_pay - prev.gross_pay) / prev.gross_pay
        if pct_change > GROSS_INCREASE_THRESHOLD:
            flagged.append(row.employee_id)
            if max_pct is None or pct_change > max_pct:
                max_pct = pct_change

    if not flagged:
        return []

    return [_finding(
        "IE.ANOMALY.001",
        "MEDIUM",
        "Gross pay increase exceeds 50 % vs previous period",
        (
            f"{len(flagged)} employee(s) have a gross pay increase greater than "
            f"{GROSS_INCREASE_THRESHOLD:.0%} compared with the previous payroll period."
        ),
        evidence={
            "count": len(flagged),
            "threshold_pct": GROSS_INCREASE_THRESHOLD,
            "max_increase_pct": round(max_pct, 4) if max_pct is not None else None,
        },
        suggestion=(
            "Verify that the increases are authorised (e.g. promotions, bonuses, "
            "back-pay). Investigate any unplanned large increases before processing."
        ),
        employee_refs=sorted(flagged)[:200],
    )]


# ---------------------------------------------------------------------------
# ANOMALY.002 — gross pay decrease > 40 %
# ---------------------------------------------------------------------------

def rule_anomaly_002_gross_pay_decrease(
    current: List[CanonicalPayrollRow],
    previous: List[CanonicalPayrollRow],
) -> List[dict]:
    """Flag employees whose gross pay decreased by more than 40 % vs the prior period."""
    prev_idx = _index_by_employee(previous)
    flagged: List[str] = []
    max_pct: Optional[float] = None

    for row in current:
        prev = prev_idx.get(row.employee_id)
        if prev is None or prev.gross_pay <= 0:
            continue
        pct_change = (prev.gross_pay - row.gross_pay) / prev.gross_pay
        if pct_change > GROSS_DECREASE_THRESHOLD:
            flagged.append(row.employee_id)
            if max_pct is None or pct_change > max_pct:
                max_pct = pct_change

    if not flagged:
        return []

    return [_finding(
        "IE.ANOMALY.002",
        "MEDIUM",
        "Gross pay decrease exceeds 40 % vs previous period",
        (
            f"{len(flagged)} employee(s) have a gross pay decrease greater than "
            f"{GROSS_DECREASE_THRESHOLD:.0%} compared with the previous payroll period."
        ),
        evidence={
            "count": len(flagged),
            "threshold_pct": GROSS_DECREASE_THRESHOLD,
            "max_decrease_pct": round(max_pct, 4) if max_pct is not None else None,
        },
        suggestion=(
            "Confirm the reductions are intentional (e.g. unpaid leave, part-time "
            "changes). Unexpected drops may indicate data-entry errors or missing pay."
        ),
        employee_refs=sorted(flagged)[:200],
    )]


# ---------------------------------------------------------------------------
# ANOMALY.003 — hours worked increase > 2×
# ---------------------------------------------------------------------------

def rule_anomaly_003_hours_increase(
    current: List[CanonicalPayrollRow],
    previous: List[CanonicalPayrollRow],
) -> List[dict]:
    """Flag employees whose reported hours more than doubled vs the prior period."""
    prev_idx = _index_by_employee(previous)
    flagged: List[str] = []
    max_ratio: Optional[float] = None

    for row in current:
        if row.hours is None or row.hours <= 0:
            continue
        prev = prev_idx.get(row.employee_id)
        if prev is None or prev.hours is None or prev.hours <= 0:
            continue
        ratio = row.hours / prev.hours
        if ratio > HOURS_INCREASE_MULTIPLIER:
            flagged.append(row.employee_id)
            if max_ratio is None or ratio > max_ratio:
                max_ratio = ratio

    if not flagged:
        return []

    return [_finding(
        "IE.ANOMALY.003",
        "MEDIUM",
        "Hours worked more than doubled vs previous period",
        (
            f"{len(flagged)} employee(s) recorded more than "
            f"{HOURS_INCREASE_MULTIPLIER:.0f}× their previous period hours."
        ),
        evidence={
            "count": len(flagged),
            "multiplier_threshold": HOURS_INCREASE_MULTIPLIER,
            "max_ratio": round(max_ratio, 4) if max_ratio is not None else None,
        },
        suggestion=(
            "Review timesheets for the affected employees. Ensure overtime and "
            "additional shifts are correctly approved and recorded."
        ),
        employee_refs=sorted(flagged)[:200],
    )]


# ---------------------------------------------------------------------------
# ANOMALY.004 — negative net pay
# ---------------------------------------------------------------------------

def rule_anomaly_004_negative_net_pay(
    current: List[CanonicalPayrollRow],
    previous: List[CanonicalPayrollRow],  # noqa: ARG001 — kept for uniform signature
) -> List[dict]:
    """Flag any employee with a negative net pay in the current payroll."""
    flagged = [r.employee_id for r in current if r.net_pay < 0]

    if not flagged:
        return []

    min_net = min(r.net_pay for r in current if r.net_pay < 0)

    return [_finding(
        "IE.ANOMALY.004",
        "MEDIUM",
        "Negative net pay detected",
        (
            f"{len(flagged)} employee(s) have a negative net pay in the current "
            "payroll period."
        ),
        evidence={
            "count": len(flagged),
            "min_net_pay": round(min_net, 2),
        },
        suggestion=(
            "Negative net pay typically arises from over-deductions or salary "
            "advances. Confirm deduction totals are correct before finalising payroll."
        ),
        amount_impact=round(abs(min_net), 2),
        employee_refs=sorted(flagged)[:200],
    )]


# ---------------------------------------------------------------------------
# ANOMALY.005 — unusually high pay for new employee
# ---------------------------------------------------------------------------

def rule_anomaly_005_new_employee_high_pay(
    current: List[CanonicalPayrollRow],
    previous: List[CanonicalPayrollRow],
) -> List[dict]:
    """Flag new employees (absent from previous payroll) with unusually high gross pay.

    "Unusually high" is defined as exceeding NEW_EMP_HIGH_PAY_MULTIPLIER times
    the mean gross pay of employees present in the previous period.  When there
    is no previous-period data the absolute ANOMALY_005_FALLBACK_THRESHOLD is
    used instead.
    """
    prev_ids = {r.employee_id for r in previous}
    new_employees = [r for r in current if r.employee_id not in prev_ids]

    if not new_employees:
        return []

    # Derive threshold
    if previous:
        mean_prev_gross = sum(r.gross_pay for r in previous) / len(previous)
        threshold = mean_prev_gross * NEW_EMP_HIGH_PAY_MULTIPLIER
    else:
        mean_prev_gross = None
        threshold = ANOMALY_005_FALLBACK_THRESHOLD

    flagged = [r.employee_id for r in new_employees if r.gross_pay > threshold]

    if not flagged:
        return []

    max_gross = max(r.gross_pay for r in new_employees if r.employee_id in set(flagged))

    return [_finding(
        "IE.ANOMALY.005",
        "MEDIUM",
        "Unusually high gross pay for new employee",
        (
            f"{len(flagged)} new employee(s) have a gross pay exceeding the "
            f"anomaly threshold of {threshold:,.2f} "
            f"({NEW_EMP_HIGH_PAY_MULTIPLIER:.0f}× previous-period mean)."
        ),
        evidence={
            "count": len(flagged),
            "threshold": round(threshold, 2),
            "mean_prev_gross": round(mean_prev_gross, 2) if mean_prev_gross is not None else None,
            "multiplier": NEW_EMP_HIGH_PAY_MULTIPLIER,
            "max_new_employee_gross": round(max_gross, 2),
        },
        suggestion=(
            "Verify that the starting salary for new hire(s) has been correctly "
            "entered and approved. Unusually high first-period pay can indicate "
            "data-entry errors or an incorrect pay-grade assignment."
        ),
        employee_refs=sorted(flagged)[:200],
    )]


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def run_anomaly_checks(
    current: List[CanonicalPayrollRow],
    previous: List[CanonicalPayrollRow],
) -> List[dict]:
    """Run all anomaly rules in canonical order and return combined findings."""
    findings: List[dict] = []
    findings += rule_anomaly_001_gross_pay_increase(current, previous)
    findings += rule_anomaly_002_gross_pay_decrease(current, previous)
    findings += rule_anomaly_003_hours_increase(current, previous)
    findings += rule_anomaly_004_negative_net_pay(current, previous)
    findings += rule_anomaly_005_new_employee_high_pay(current, previous)
    return findings
