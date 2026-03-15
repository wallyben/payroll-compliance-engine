"""
core/reporting/exposure_engine.py
----------------------------------
Deterministic financial exposure quantification module.

Consumes findings produced by core/rules.engine.run_all().
Does NOT modify rule logic or scoring logic.

Finding structure (as produced by core/rules/rules.py _finding() helper):
    {
        "rule_id":       str,             # e.g. "IE.MINWAGE.001"
        "severity":      str,             # "HIGH" | "MEDIUM" | "LOW"
        "title":         str,
        "description":   str,
        "evidence":      dict,
        "suggestion":    str,
        "amount_impact": float | None,    # financial exposure; None treated as 0
        "employee_refs": List[str],       # employee identifiers involved
    }
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


def quantify_exposure(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a list of rule findings into estimated financial exposure.

    Parameters
    ----------
    findings:
        Findings as produced by core/rules.engine.run_all().

    Returns
    -------
    {
        "exposure_total":     float,            – sum of all amount_impact values
        "employees_impacted": int,              – count of distinct employee IDs
        "exposure_by_rule":   Dict[str, float]  – per-rule exposure totals (sorted)
    }

    Output is fully deterministic: identical inputs always produce identical outputs.
    No randomness is introduced at any point.
    """
    exposure_by_rule: Dict[str, float] = defaultdict(float)
    unique_employees: set[str] = set()

    for finding in findings:
        rule_id: str = finding.get("rule_id", "UNKNOWN")
        amount: float = _safe_amount(finding)
        employee_refs: List[str] = finding.get("employee_refs") or []

        exposure_by_rule[rule_id] += amount
        unique_employees.update(employee_refs)

    # Sort keys for deterministic ordering across all Python versions
    sorted_exposure_by_rule: Dict[str, float] = dict(sorted(exposure_by_rule.items()))

    exposure_total: float = round(sum(sorted_exposure_by_rule.values()), 2)

    return {
        "exposure_total": exposure_total,
        "employees_impacted": len(unique_employees),
        "exposure_by_rule": sorted_exposure_by_rule,
    }


def _safe_amount(finding: Dict[str, Any]) -> float:
    """Extract a non-negative numeric exposure from a finding.

    Returns 0.0 for None, missing keys, non-numeric values, or NaN.
    """
    raw = finding.get("amount_impact")
    if raw is None:
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    # Reject NaN without importing math
    if value != value:
        return 0.0
    return value
