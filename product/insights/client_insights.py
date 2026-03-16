"""product/insights/client_insights.py
---------------------------------------
Generates operational insights for payroll bureaux.

Insights are aggregated from the stored payroll run history; no compliance
or payroll logic is re-implemented here.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.analysis.client_risk_timeline import analyze_client_risk_timeline
from core.domain.payroll_run import PayrollRun, get_client_runs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_client_insights(client_id: str) -> Dict[str, Any]:
    """Generate operational insights for *client_id* across all stored runs.

    Returns
    -------
    {
        "average_risk_score":      float   – mean risk_score across all runs
        "risk_trend":              str     – "INCREASING" | "DECREASING" | "STABLE"
        "runs_analyzed":           int     – total payroll runs in history
        "most_common_violations":  list    – [{"rule_id": str, "count": int}, ...]
        "average_employee_count":  float   – mean employee headcount per run
        "payroll_growth_rate":     float   – avg period-over-period % growth in gross pay
    }
    """
    client_runs: List[PayrollRun] = get_client_runs(client_id)

    if not client_runs:
        return {
            "average_risk_score": 0.0,
            "risk_trend": "STABLE",
            "runs_analyzed": 0,
            "most_common_violations": [],
            "average_employee_count": 0.0,
            "payroll_growth_rate": 0.0,
        }

    timeline = analyze_client_risk_timeline(client_runs)

    avg_employee_count = round(
        sum(len(r.normalized_rows) for r in client_runs) / len(client_runs), 4
    )
    payroll_growth_rate = _compute_payroll_growth_rate(client_runs)

    return {
        "average_risk_score": timeline["average_risk_score"],
        "risk_trend": timeline["risk_trend"],
        "runs_analyzed": timeline["runs_analyzed"],
        "most_common_violations": timeline["most_common_violations"],
        "average_employee_count": avg_employee_count,
        "payroll_growth_rate": payroll_growth_rate,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_payroll_growth_rate(runs: List[PayrollRun]) -> float:
    """Return the average period-over-period gross payroll growth rate (%).

    Computes the overall percentage change from the first to the last run
    and divides by the number of intervals to give a per-period average.
    Returns 0.0 when fewer than two runs are available or when the first
    run's total gross is zero.
    """
    if len(runs) < 2:
        return 0.0

    def _total_gross(run: PayrollRun) -> float:
        return sum(row.gross_pay for row in run.normalized_rows)

    totals = [_total_gross(r) for r in runs]
    first_total = totals[0]
    if first_total == 0.0:
        return 0.0

    last_total = totals[-1]
    overall_pct_change = ((last_total - first_total) / first_total) * 100.0
    num_intervals = len(runs) - 1
    return round(overall_pct_change / num_intervals, 4)
