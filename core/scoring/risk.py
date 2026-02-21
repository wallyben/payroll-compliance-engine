from __future__ import annotations
from typing import Dict, List, Any, Tuple

# Deterministic, auditable scoring.
# No heuristics. No model inference. Pure severity weighting.

DEFAULT_SEVERITY_WEIGHTS: Dict[str, int] = {
    "HIGH": 10,
    "MEDIUM": 4,
    "LOW": 1,
}

def summarize_findings(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_rule: Dict[str, int] = {}

    for f in findings:
        sev = (f.get("severity") or "").upper()
        if sev in counts:
            counts[sev] += 1
        rid = f.get("rule_id") or "UNKNOWN"
        by_rule[rid] = by_rule.get(rid, 0) + 1

    return {
        "counts_by_severity": counts,
        "counts_by_rule": by_rule,
        "total_findings": len(findings),
    }

def risk_points(findings: List[Dict[str, Any]], weights: Dict[str, int] | None = None) -> int:
    w = weights or DEFAULT_SEVERITY_WEIGHTS
    points = 0
    for f in findings:
        sev = (f.get("severity") or "").upper()
        points += int(w.get(sev, 0))
    return points

def compliance_score(findings: List[Dict[str, Any]], max_points: int = 100) -> int:
    # Deterministic score 0..100:
    # - 0 points => 100 score
    # - >= max_points => 0 score
    pts = risk_points(findings)
    score = max(0, 100 - int(round((pts / max_points) * 100)))
    return min(100, score)

def score_bundle(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summarize_findings(findings)
    pts = risk_points(findings)
    score = compliance_score(findings)
    return {
        "risk_points": pts,
        "compliance_score": score,
        **summary,
    }
