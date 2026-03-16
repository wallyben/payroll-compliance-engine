"""product/dashboards/client_dashboard.py
-----------------------------------------
Aggregates payroll run data for the payroll specialist dashboard.

The dashboard is a read-only projection; it does not implement any
compliance or payroll logic — it only consumes outputs already stored
by the review engine.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.analysis.client_risk_timeline import analyze_client_risk_timeline
from core.domain.payroll_run import get_client_runs
from core.reporting.exposure_engine import quantify_exposure
from product.workflow.payroll_workflow import get_client_workflow_history


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_client_dashboard(client_id: str) -> Dict[str, Any]:
    """Build an aggregated dashboard view for *client_id*.

    Returns
    -------
    {
        "client_id":           str   – supplied client identifier
        "latest_run_date":     str | None  – ISO-8601 period_end of most recent run
        "latest_review_status": str | None – workflow state label of most recent run
        "risk_score":          float – raw risk_points of the most recent run
        "exposure_total":      float – sum of amount_impact across latest run findings
        "employee_count":      int   – number of employees in the latest run
        "issues_detected":     int   – total findings count in the latest run
        "trend":               str   – "INCREASING" | "DECREASING" | "STABLE"
    }
    """
    client_runs = get_client_runs(client_id)

    if not client_runs:
        return {
            "client_id": client_id,
            "latest_run_date": None,
            "latest_review_status": None,
            "risk_score": 0.0,
            "exposure_total": 0.0,
            "employee_count": 0,
            "issues_detected": 0,
            "trend": "STABLE",
        }

    latest_run = client_runs[-1]
    timeline = analyze_client_risk_timeline(client_runs)
    exposure = quantify_exposure(latest_run.findings)

    latest_review_status = _resolve_latest_review_status(client_id, latest_run.run_id)

    return {
        "client_id": client_id,
        "latest_run_date": latest_run.period_end.isoformat(),
        "latest_review_status": latest_review_status,
        "risk_score": latest_run.risk_score,
        "exposure_total": round(exposure["exposure_total"], 2),
        "employee_count": len(latest_run.normalized_rows),
        "issues_detected": len(latest_run.findings),
        "trend": timeline["risk_trend"],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_latest_review_status(client_id: str, latest_run_id: str) -> Optional[str]:
    """Return the workflow state label for the most recent run.

    Prefers an exact run_id match; falls back to the most recently created
    workflow record for the client when the run_id has no record yet.
    """
    workflow_history = get_client_workflow_history(client_id)
    if not workflow_history:
        return "REVIEWING"

    # Prefer exact match for the latest run.
    for record in reversed(workflow_history):
        if record.run_id == latest_run_id:
            return record.state.value

    # Fall back to most recently created record.
    return workflow_history[-1].state.value
