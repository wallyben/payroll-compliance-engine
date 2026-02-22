"""Build scan summary and categorize findings. No rule or scoring logic."""
from typing import List, Dict, Any

# Map engine severity to summary buckets
SEVERITY_MAP = {"HIGH": "critical", "MEDIUM": "warning", "LOW": "info"}


def _severity_bucket(f: Dict[str, Any]) -> str:
    return SEVERITY_MAP.get((f.get("severity") or "").upper(), "info")


def _is_auto_enrolment(rule_id: str) -> bool:
    return (rule_id or "").startswith("IE.AUTO")


def _is_revenue(rule_id: str) -> bool:
    r = (rule_id or "")
    return any(r.startswith(p) for p in ("IE.PAYE", "IE.USC", "IE.PRSI", "IE.SANITY"))


def build_scan_summary(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    critical = sum(1 for f in findings if _severity_bucket(f) == "critical")
    warning = sum(1 for f in findings if _severity_bucket(f) == "warning")
    info = sum(1 for f in findings if _severity_bucket(f) == "info")
    if critical > 0:
        overall = "RED"
    elif warning > 0:
        overall = "AMBER"
    else:
        overall = "GREEN"
    return {
        "total_findings": len(findings),
        "critical": critical,
        "warning": warning,
        "info": info,
        "overall": overall,
    }


def split_findings(findings: List[Dict[str, Any]]) -> tuple:
    auto_enrolment = [f for f in findings if _is_auto_enrolment(f.get("rule_id", ""))]
    revenue = [f for f in findings if _is_revenue(f.get("rule_id", ""))]
    return auto_enrolment, revenue
