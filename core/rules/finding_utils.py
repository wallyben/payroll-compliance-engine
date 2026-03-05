"""Shared finding builder. Same shape as existing rules._finding for API/exposure."""
from __future__ import annotations
from typing import Any, List, Optional


def finding(
    rule_id: str,
    severity: str,
    title: str,
    description: str,
    *,
    evidence: Optional[dict] = None,
    suggestion: str = "",
    amount_impact: Optional[float] = None,
    employee_refs: Optional[List[str]] = None,
    category: Optional[str] = None,
) -> dict:
    """Build a finding dict compatible with API Finding and exposure engine."""
    out: dict[str, Any] = {
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        "description": description,
        "evidence": evidence or {},
        "suggestion": suggestion,
        "amount_impact": amount_impact,
        "employee_refs": employee_refs or [],
    }
    if category is not None:
        out["category"] = category
    return out
