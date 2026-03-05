"""Arithmetic file-level rule: IE.TOTALS.001."""
from __future__ import annotations
from typing import List
from core.normalize.schema import CanonicalPayrollRow
from core.rules.finding_utils import finding


def _total_deductions(r: CanonicalPayrollRow) -> float:
    if r.total_deductions is not None:
        return r.total_deductions
    return (r.paye or 0) + (r.usc or 0) + (r.prsi_ee or 0) + (r.pension_ee or 0)


def rule_ie_totals_001(rows: List[CanonicalPayrollRow], tolerance: float = 0.02) -> List[dict]:
    """IE.TOTALS.001: SUM(gross_pay) - SUM(total_deductions) != SUM(net_pay). File-level. CRITICAL."""
    if not rows:
        return []
    sum_gross = sum(r.gross_pay for r in rows)
    sum_deductions = sum(_total_deductions(r) for r in rows)
    sum_net = sum(r.net_pay for r in rows)
    expected_net = sum_gross - sum_deductions
    if abs(sum_net - expected_net) > tolerance:
        return [finding(
            "IE.TOTALS.001",
            "CRITICAL",
            "File-level gross minus deductions != net",
            "SUM(gross_pay) - SUM(total_deductions) != SUM(net_pay)",
            evidence={
                "sum_gross_pay": sum_gross,
                "sum_total_deductions": sum_deductions,
                "sum_net_pay": sum_net,
                "expected_net": expected_net,
                "tolerance": tolerance,
            },
            suggestion="Reconcile file totals; allow small floating tolerance.",
            amount_impact=sum_net - expected_net,
            employee_refs=[r.employee_id for r in rows[:200]],
            category="TOTALS",
        )]
    return []
