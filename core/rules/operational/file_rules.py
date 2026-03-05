"""Operational file-level rule: IE.DATA.001 duplicate employee."""
from __future__ import annotations
from typing import List
from collections import Counter
from core.normalize.schema import CanonicalPayrollRow
from core.rules.finding_utils import finding


def rule_ie_data_001(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.DATA.001: Duplicate employee_id within payroll file. HIGH."""
    if not rows:
        return []
    counts = Counter(r.employee_id for r in rows)
    duplicates = [eid for eid, c in counts.items() if c > 1]
    if not duplicates:
        return []
    return [finding(
        "IE.DATA.001",
        "HIGH",
        "Duplicate employee within payroll file",
        "Duplicate employee_id in same file",
        evidence={"duplicate_employee_ids": duplicates[:200], "count": len(duplicates)},
        suggestion="Deduplicate rows per employee per period.",
        employee_refs=duplicates[:200],
        category="DATA",
    )]
