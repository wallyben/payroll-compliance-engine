from __future__ import annotations

from typing import Any, Dict, List

from core.domain.payroll_run import PayrollRun

# Runs with a risk_score at or above this threshold are counted as high-risk.
# risk_score is expressed in raw risk-points (higher = more risk), so 50 points
# corresponds to five HIGH-severity findings or twelve MEDIUM-severity findings.
HIGH_RISK_THRESHOLD: float = 50.0


def analyze_client_risk_timeline(runs: List[PayrollRun]) -> Dict[str, Any]:
    """Analyze risk trends across payroll runs for a client.

    Parameters
    ----------
    runs:
        Payroll runs to analyze — may arrive in any order.  Each run must
        carry a ``risk_score`` (raw risk-points, higher = more risk) and a
        ``findings`` list.

    Returns
    -------
    dict with keys:
        risk_trend            – "INCREASING" | "DECREASING" | "STABLE"
        average_risk_score    – mean risk_score across all runs (float, 4 dp)
        runs_analyzed         – total number of runs supplied
        high_risk_runs        – count of runs where risk_score >= HIGH_RISK_THRESHOLD
        most_common_violations – list of {"rule_id": str, "count": int}, ordered
                                 by frequency descending then rule_id ascending
    """
    if not runs:
        return {
            "risk_trend": "STABLE",
            "average_risk_score": 0.0,
            "runs_analyzed": 0,
            "high_risk_runs": 0,
            "most_common_violations": [],
        }

    # Sort chronologically for all subsequent calculations.
    sorted_runs = sorted(runs, key=lambda r: r.period_end)

    scores = [r.risk_score for r in sorted_runs]

    average_risk_score = round(sum(scores) / len(scores), 4)
    high_risk_runs = sum(1 for s in scores if s >= HIGH_RISK_THRESHOLD)

    # Violation frequency: count rule_id across every finding in every run.
    # Ties broken alphabetically by rule_id for determinism.
    violation_counts: Dict[str, int] = {}
    for run in sorted_runs:
        for finding in run.findings:
            rule_id = finding.get("rule_id") or "UNKNOWN"
            violation_counts[rule_id] = violation_counts.get(rule_id, 0) + 1

    most_common_violations = [
        {"rule_id": rid, "count": cnt}
        for rid, cnt in sorted(violation_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    # Trend: evaluate the direction across the last 3 runs.
    window_scores = scores[-3:]
    risk_trend = _compute_trend(window_scores)

    return {
        "risk_trend": risk_trend,
        "average_risk_score": average_risk_score,
        "runs_analyzed": len(sorted_runs),
        "high_risk_runs": high_risk_runs,
        "most_common_violations": most_common_violations,
    }


def _compute_trend(scores: List[float]) -> str:
    """Return "INCREASING", "DECREASING", or "STABLE" for an ordered score list.

    Requires at least two scores to detect a direction; a single-element list
    is always STABLE.  Both consecutive pairs must agree in direction for a
    non-STABLE result to be returned.
    """
    if len(scores) < 2:
        return "STABLE"

    diffs = [scores[i + 1] - scores[i] for i in range(len(scores) - 1)]

    if all(d > 0 for d in diffs):
        return "INCREASING"
    if all(d < 0 for d in diffs):
        return "DECREASING"
    return "STABLE"
