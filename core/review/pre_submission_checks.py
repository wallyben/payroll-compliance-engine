from __future__ import annotations

import re
from typing import List, Optional

from core.normalize.schema import CanonicalPayrollRow

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_SALARY_SPIKE_THRESHOLD = 0.20       # gross_pay increase > 20 %
_SALARY_DROP_THRESHOLD = 0.20        # gross_pay decrease > 20 %
_HOURS_SPIKE_FACTOR = 2.0            # hours > 2× previous
_HOURS_DROP_THRESHOLD = 0.50         # hours drop > 50 %
_NET_CHANGE_THRESHOLD = 0.30         # net_pay change > 30 %
_TOTAL_PAYROLL_THRESHOLD = 0.15      # total gross change > 15 %

# Irish PPSN: 7 digits + 1 uppercase letter + optional second uppercase letter
_PPSN_RE = re.compile(r"^\d{7}[A-Z]{1,2}$")

# Deterministic finding order — one entry per check, in this fixed sequence
_RULE_ORDER = [
    "QA.POP.001",  # new employees
    "QA.POP.002",  # removed employees
    "QA.POP.003",  # duplicate employee IDs
    "QA.SAL.001",  # salary increase > 20 %
    "QA.SAL.002",  # salary decrease > 20 %
    "QA.HRS.001",  # hours spike > 2×
    "QA.HRS.002",  # hours drop > 50 %
    "QA.NET.001",  # negative net pay
    "QA.NET.002",  # net > gross
    "QA.NET.003",  # net change > 30 %
    "QA.TOT.001",  # total payroll change > 15 %
    "QA.STAT.001", # missing PPSN
    "QA.STAT.002", # invalid PPSN format
    "QA.STAT.003", # missing PRSI class
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _finding(
    rule_id: str,
    severity: str,
    title: str,
    description: str,
    *,
    evidence: dict | None = None,
    suggestion: str = "",
    amount_impact: Optional[float] = None,
    employee_refs: list[str] | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        "description": description,
        "evidence": evidence or {},
        "suggestion": suggestion,
        "amount_impact": amount_impact,
        "employee_refs": sorted(employee_refs) if employee_refs else [],
    }


def _pct(numerator: float, denominator: float) -> float:
    return round(numerator / abs(denominator) * 100, 4)


# ---------------------------------------------------------------------------
# Individual check functions  (each returns one finding or None)
# ---------------------------------------------------------------------------

def _check_new_employees(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    new_ids = sorted(set(curr_by_id) - set(prev_by_id))
    if not new_ids:
        return None
    return _finding(
        "QA.POP.001",
        "LOW",
        "New employees detected",
        f"{len(new_ids)} employee(s) appear in the current payroll but were absent from the previous period.",
        evidence={"count": len(new_ids)},
        suggestion="Confirm new starters are intentional and properly onboarded.",
        employee_refs=new_ids,
    )


def _check_removed_employees(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    removed_ids = sorted(set(prev_by_id) - set(curr_by_id))
    if not removed_ids:
        return None
    return _finding(
        "QA.POP.002",
        "MEDIUM",
        "Employees removed from payroll",
        f"{len(removed_ids)} employee(s) present in the previous period are absent from the current payroll.",
        evidence={"count": len(removed_ids)},
        suggestion="Confirm leavers are intentional; check for accidental omissions.",
        employee_refs=removed_ids,
    )


def _check_duplicate_employees(
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    seen: dict[str, int] = {}
    for r in current_rows:
        seen[r.employee_id] = seen.get(r.employee_id, 0) + 1
    duplicates = sorted(eid for eid, cnt in seen.items() if cnt > 1)
    if not duplicates:
        return None
    return _finding(
        "QA.POP.003",
        "HIGH",
        "Duplicate employee IDs in current payroll",
        f"{len(duplicates)} employee ID(s) appear more than once in the current payroll dataset.",
        evidence={"counts": {eid: seen[eid] for eid in duplicates}},
        suggestion="Remove duplicate rows before submission; each employee_id must be unique per period.",
        employee_refs=duplicates,
    )


def _check_salary_increase(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    flagged: list[str] = []
    evidence_detail: dict[str, dict] = {}
    for eid in sorted(set(prev_by_id) & set(curr_by_id)):
        prev_gp = prev_by_id[eid].gross_pay
        curr_gp = curr_by_id[eid].gross_pay
        if prev_gp == 0.0:
            continue
        if (curr_gp - prev_gp) / abs(prev_gp) > _SALARY_SPIKE_THRESHOLD:
            flagged.append(eid)
            evidence_detail[eid] = {
                "previous_gross_pay": prev_gp,
                "current_gross_pay": curr_gp,
                "percent_change": _pct(curr_gp - prev_gp, prev_gp),
            }
    if not flagged:
        return None
    return _finding(
        "QA.SAL.001",
        "MEDIUM",
        "Salary increase exceeds 20 %",
        f"{len(flagged)} employee(s) have a gross pay increase greater than 20 % versus the previous period.",
        evidence={"count": len(flagged), "employees": evidence_detail},
        suggestion="Verify salary changes are authorised; check for mapping errors or duplicate bonuses.",
        employee_refs=flagged,
    )


def _check_salary_decrease(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    flagged: list[str] = []
    evidence_detail: dict[str, dict] = {}
    for eid in sorted(set(prev_by_id) & set(curr_by_id)):
        prev_gp = prev_by_id[eid].gross_pay
        curr_gp = curr_by_id[eid].gross_pay
        if prev_gp == 0.0:
            continue
        if (prev_gp - curr_gp) / abs(prev_gp) > _SALARY_DROP_THRESHOLD:
            flagged.append(eid)
            evidence_detail[eid] = {
                "previous_gross_pay": prev_gp,
                "current_gross_pay": curr_gp,
                "percent_change": _pct(curr_gp - prev_gp, prev_gp),
            }
    if not flagged:
        return None
    return _finding(
        "QA.SAL.002",
        "MEDIUM",
        "Salary decrease exceeds 20 %",
        f"{len(flagged)} employee(s) have a gross pay decrease greater than 20 % versus the previous period.",
        evidence={"count": len(flagged), "employees": evidence_detail},
        suggestion="Confirm salary reductions are authorised; check for partial-period or missing pay components.",
        employee_refs=flagged,
    )


def _check_hours_spike(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    flagged: list[str] = []
    evidence_detail: dict[str, dict] = {}
    for eid in sorted(set(prev_by_id) & set(curr_by_id)):
        prev_h = prev_by_id[eid].hours
        curr_h = curr_by_id[eid].hours
        if prev_h is None or curr_h is None or prev_h == 0.0:
            continue
        if curr_h / prev_h > _HOURS_SPIKE_FACTOR:
            flagged.append(eid)
            evidence_detail[eid] = {
                "previous_hours": prev_h,
                "current_hours": curr_h,
                "factor": round(curr_h / prev_h, 4),
            }
    if not flagged:
        return None
    return _finding(
        "QA.HRS.001",
        "HIGH",
        "Hours spike: current hours exceed 2× previous period",
        f"{len(flagged)} employee(s) have hours more than double those of the previous period.",
        evidence={"count": len(flagged), "employees": evidence_detail},
        suggestion="Verify overtime authorisation; check for duplicate time entries or period boundary errors.",
        employee_refs=flagged,
    )


def _check_hours_drop(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    flagged: list[str] = []
    evidence_detail: dict[str, dict] = {}
    for eid in sorted(set(prev_by_id) & set(curr_by_id)):
        prev_h = prev_by_id[eid].hours
        curr_h = curr_by_id[eid].hours
        if prev_h is None or curr_h is None or prev_h == 0.0:
            continue
        if (prev_h - curr_h) / abs(prev_h) > _HOURS_DROP_THRESHOLD:
            flagged.append(eid)
            evidence_detail[eid] = {
                "previous_hours": prev_h,
                "current_hours": curr_h,
                "percent_drop": _pct(prev_h - curr_h, prev_h),
            }
    if not flagged:
        return None
    return _finding(
        "QA.HRS.002",
        "MEDIUM",
        "Hours drop exceeds 50 %",
        f"{len(flagged)} employee(s) have hours more than 50 % below the previous period.",
        evidence={"count": len(flagged), "employees": evidence_detail},
        suggestion="Confirm leave, reduced hours, or termination; check for missing time submissions.",
        employee_refs=flagged,
    )


def _check_negative_net_pay(
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    flagged = sorted(r.employee_id for r in current_rows if r.net_pay < 0.0)
    if not flagged:
        return None
    return _finding(
        "QA.NET.001",
        "HIGH",
        "Negative net pay",
        f"{len(flagged)} employee(s) have a negative net pay value in the current payroll.",
        evidence={"count": len(flagged)},
        suggestion="Negative net pay indicates excessive deductions or a data error; investigate before submission.",
        employee_refs=flagged,
    )


def _check_net_exceeds_gross(
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    tol = 0.01
    flagged = sorted(
        r.employee_id for r in current_rows if r.net_pay > r.gross_pay + tol
    )
    if not flagged:
        return None
    return _finding(
        "QA.NET.002",
        "HIGH",
        "Net pay exceeds gross pay",
        f"{len(flagged)} employee(s) have net pay greater than gross pay, which is arithmetically impossible.",
        evidence={"count": len(flagged)},
        suggestion="Check for swapped gross/net columns or incorrect deduction sign conventions.",
        employee_refs=flagged,
    )


def _check_net_change(
    prev_by_id: dict[str, CanonicalPayrollRow],
    curr_by_id: dict[str, CanonicalPayrollRow],
) -> dict | None:
    flagged: list[str] = []
    evidence_detail: dict[str, dict] = {}
    for eid in sorted(set(prev_by_id) & set(curr_by_id)):
        prev_np = prev_by_id[eid].net_pay
        curr_np = curr_by_id[eid].net_pay
        if prev_np == 0.0:
            continue
        pct = (curr_np - prev_np) / abs(prev_np)
        if abs(pct) > _NET_CHANGE_THRESHOLD:
            flagged.append(eid)
            evidence_detail[eid] = {
                "previous_net_pay": prev_np,
                "current_net_pay": curr_np,
                "percent_change": round(pct * 100, 4),
            }
    if not flagged:
        return None
    return _finding(
        "QA.NET.003",
        "MEDIUM",
        "Net pay change exceeds 30 %",
        f"{len(flagged)} employee(s) have a net pay movement greater than 30 % versus the previous period.",
        evidence={"count": len(flagged), "employees": evidence_detail},
        suggestion="Large net pay swings may indicate deduction mapping errors or tax band changes; verify before submission.",
        employee_refs=flagged,
    )


def _check_total_payroll_change(
    previous_rows: List[CanonicalPayrollRow],
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    previous_total = sum(r.gross_pay for r in previous_rows)
    current_total = sum(r.gross_pay for r in current_rows)
    if previous_total == 0.0:
        return None
    pct = (current_total - previous_total) / abs(previous_total)
    if abs(pct) <= _TOTAL_PAYROLL_THRESHOLD:
        return None
    return _finding(
        "QA.TOT.001",
        "HIGH",
        "Total payroll change exceeds 15 %",
        f"Total gross payroll moved by {round(pct * 100, 2)} % versus the previous period "
        f"(€{round(previous_total, 2)} → €{round(current_total, 2)}).",
        evidence={
            "previous_total": round(previous_total, 2),
            "current_total": round(current_total, 2),
            "absolute_change": round(current_total - previous_total, 2),
            "percent_change": round(pct * 100, 4),
        },
        suggestion="A large aggregate swing warrants manual sign-off before submission to Revenue.",
        amount_impact=round(abs(current_total - previous_total), 2),
    )


def _check_missing_ppsn(
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    flagged = sorted(
        r.employee_id for r in current_rows if not r.ppsn or not r.ppsn.strip()
    )
    if not flagged:
        return None
    return _finding(
        "QA.STAT.001",
        "MEDIUM",
        "Missing PPSN",
        f"{len(flagged)} employee(s) have no PPSN recorded in the current payroll.",
        evidence={"count": len(flagged)},
        suggestion="PPSN is required for Revenue reporting; obtain and record before submission.",
        employee_refs=flagged,
    )


def _check_invalid_ppsn(
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    flagged: list[str] = []
    for r in current_rows:
        if not r.ppsn or not r.ppsn.strip():
            continue  # already caught by QA.STAT.001
        if not _PPSN_RE.match(r.ppsn.strip().upper()):
            flagged.append(r.employee_id)
    flagged = sorted(flagged)
    if not flagged:
        return None
    return _finding(
        "QA.STAT.002",
        "HIGH",
        "Invalid PPSN format",
        f"{len(flagged)} employee(s) have a PPSN that does not match the expected format (7 digits + 1–2 letters).",
        evidence={"count": len(flagged)},
        suggestion="Correct malformed PPSNs before submission; Revenue will reject records with invalid identifiers.",
        employee_refs=flagged,
    )


def _check_missing_prsi_class(
    current_rows: List[CanonicalPayrollRow],
) -> dict | None:
    flagged = sorted(
        r.employee_id
        for r in current_rows
        if not r.prsi_class or not r.prsi_class.strip()
    )
    if not flagged:
        return None
    return _finding(
        "QA.STAT.003",
        "MEDIUM",
        "Missing PRSI class",
        f"{len(flagged)} employee(s) have no PRSI class recorded in the current payroll.",
        evidence={"count": len(flagged)},
        suggestion="PRSI class determines contribution rates; assign the correct class before submission.",
        employee_refs=flagged,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pre_submission_checks(
    previous_rows: List[CanonicalPayrollRow],
    current_rows: List[CanonicalPayrollRow],
) -> List[dict]:
    """Run all pre-submission QA checks and return a list of findings.

    Findings are in rule-ID order (see ``_RULE_ORDER``) and contain the same
    keys as the compliance rule engine so they can be consumed by the same
    scoring and reporting pipeline.

    Employee matching uses ``employee_id``.  All ``employee_refs`` lists
    inside findings are sorted for deterministic output.

    Parameters
    ----------
    previous_rows:
        Payroll rows from the immediately preceding period.  Pass an empty
        list when no previous payroll is available (first run).
    current_rows:
        Payroll rows for the period about to be submitted.

    Returns
    -------
    List of finding dicts, one per triggered check, in a fixed order.
    An empty list means the payroll passed all checks.
    """
    prev_by_id: dict[str, CanonicalPayrollRow] = {r.employee_id: r for r in previous_rows}
    curr_by_id: dict[str, CanonicalPayrollRow] = {r.employee_id: r for r in current_rows}

    candidates: list[dict | None] = [
        _check_new_employees(prev_by_id, curr_by_id),
        _check_removed_employees(prev_by_id, curr_by_id),
        _check_duplicate_employees(current_rows),
        _check_salary_increase(prev_by_id, curr_by_id),
        _check_salary_decrease(prev_by_id, curr_by_id),
        _check_hours_spike(prev_by_id, curr_by_id),
        _check_hours_drop(prev_by_id, curr_by_id),
        _check_negative_net_pay(current_rows),
        _check_net_exceeds_gross(current_rows),
        _check_net_change(prev_by_id, curr_by_id),
        _check_total_payroll_change(previous_rows, current_rows),
        _check_missing_ppsn(current_rows),
        _check_invalid_ppsn(current_rows),
        _check_missing_prsi_class(current_rows),
    ]

    return [f for f in candidates if f is not None]
