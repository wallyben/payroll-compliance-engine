"""Arithmetic row rules: IE.NET.001, IE.NET.002, IE.DEDUCT.001, IE.PENSION.002, IE.PAY.002."""
from __future__ import annotations
from typing import List, Dict, Any
from core.normalize.schema import CanonicalPayrollRow
from core.rules.finding_utils import finding


def _total_deductions(r: CanonicalPayrollRow) -> float:
    if r.total_deductions is not None:
        return r.total_deductions
    return (r.paye or 0) + (r.usc or 0) + (r.prsi_ee or 0) + (r.pension_ee or 0)


def rule_ie_net_001(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.NET.001: net_pay > gross_pay. Severity: CRITICAL."""
    out = []
    for r in rows:
        if r.net_pay > r.gross_pay + 0.01:
            out.append(finding(
                "IE.NET.001",
                "CRITICAL",
                "Net pay exceeds gross pay",
                "net_pay > gross_pay",
                suggestion="Reconcile net and gross; ensure deductions are not negative or mis-mapped.",
                amount_impact=r.net_pay - r.gross_pay,
                employee_refs=[r.employee_id],
                category="NET",
            ))
    return out


def rule_ie_net_002(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.NET.002: net_pay < 0. Severity: CRITICAL."""
    out = []
    for r in rows:
        if r.net_pay < -0.01:
            out.append(finding(
                "IE.NET.002",
                "CRITICAL",
                "Negative net pay",
                "net_pay < 0",
                suggestion="Verify deductions and reversals; net pay must not be negative for standard pay.",
                amount_impact=abs(r.net_pay),
                employee_refs=[r.employee_id],
                category="NET",
            ))
    return out


def rule_ie_deduct_001(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.DEDUCT.001: total_deductions > gross_pay. Severity: HIGH."""
    out = []
    for r in rows:
        td = _total_deductions(r)
        if td > r.gross_pay + 0.01:
            out.append(finding(
                "IE.DEDUCT.001",
                "HIGH",
                "Total deductions exceed gross pay",
                "total_deductions > gross_pay",
                evidence={"total_deductions": td, "gross_pay": r.gross_pay},
                suggestion="Verify all deduction columns and signs; total deductions cannot exceed gross.",
                amount_impact=td - r.gross_pay,
                employee_refs=[r.employee_id],
                category="DEDUCT",
            ))
    return out


def rule_ie_pension_002(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.PENSION.002: (pension_ee + pension_er) > gross_pay * 0.50. Severity: MEDIUM."""
    out = []
    for r in rows:
        total_pension = (r.pension_ee or 0) + (r.pension_er or 0)
        if r.gross_pay > 0 and total_pension > r.gross_pay * 0.50 + 0.01:
            out.append(finding(
                "IE.PENSION.002",
                "MEDIUM",
                "Pension contributions exceed 50% of gross",
                "(pension_ee + pension_er) > gross_pay * 0.50",
                evidence={"pension_ee": r.pension_ee, "pension_er": r.pension_er, "gross_pay": r.gross_pay},
                suggestion="Confirm pension rates and caps; combined pension should not exceed 50% of gross.",
                employee_refs=[r.employee_id],
                category="PENSION",
            ))
    return out


def rule_ie_pay_002(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.PAY.002: gross_pay / hours > 250. Skip if hours == 0. Severity: MEDIUM."""
    out = []
    for r in rows:
        if r.hours is None or r.hours <= 0:
            continue
        rate = r.gross_pay / r.hours
        if rate > 250.0:
            out.append(finding(
                "IE.PAY.002",
                "MEDIUM",
                "Effective hourly rate exceeds 250",
                "gross_pay / hours > 250",
                evidence={"gross_pay": r.gross_pay, "hours": r.hours, "effective_rate": rate},
                suggestion="Verify hours and gross; flag implausible rates for review.",
                employee_refs=[r.employee_id],
                category="PAY",
            ))
    return out
