"""IE.DATA.002: Missing critical fields. Runs on invalid_rows from normalization."""
from __future__ import annotations
from typing import List, Dict, Any
from core.rules.finding_utils import finding


def rule_ie_data_002_from_invalid_rows(invalid_rows: List[Dict[str, Any]]) -> List[dict]:
    """IE.DATA.002: employee_id OR gross_pay OR net_pay missing. CRITICAL. Emit per invalid row that has missing required fields."""
    out = []
    for inv in invalid_rows:
        errors = inv.get("errors") or []
        row_num = inv.get("row_number", 0)
        missing = []
        for e in errors:
            if isinstance(e, dict):
                msg = (e.get("msg") or str(e)).lower()
                if "employee_id" in msg or "gross_pay" in msg or "net_pay" in msg or "required" in msg or "missing" in msg:
                    missing.append(e.get("msg", "missing required field"))
            else:
                missing.append(str(e))
        if missing:
            out.append(finding(
                "IE.DATA.002",
                "CRITICAL",
                "Missing critical fields",
                "employee_id OR gross_pay OR net_pay missing",
                evidence={"row_number": row_num, "errors": missing[:5]},
                suggestion="Supply required fields for every row.",
                employee_refs=[],
                category="DATA",
            ))
    return out
