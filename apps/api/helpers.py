"""API-layer helpers. No compliance or scoring logic."""

from typing import Any, Dict, List


def aggregate_severity_summary(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Build Phase 3 severity summary dict from findings. Output shape: HIGH, MEDIUM, LOW, TOTAL."""
    return {
        "HIGH": sum(1 for f in findings if f.get("severity") == "HIGH"),
        "MEDIUM": sum(1 for f in findings if f.get("severity") == "MEDIUM"),
        "LOW": sum(1 for f in findings if f.get("severity") == "LOW"),
        "TOTAL": len(findings),
    }
