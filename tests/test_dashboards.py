"""tests/test_dashboards.py
Tests for product/dashboards/client_dashboard.py

Covers:
- Empty client returns zero-state dashboard
- Dashboard fields correctly reflect latest run data
- Employee count from normalized_rows
- Exposure total aggregated from findings
- Risk trend computed across multiple runs
- latest_review_status derived from workflow records
- Multi-client isolation
- Deterministic: same inputs produce identical output
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from core.domain.payroll_run import _clear_runs, create_payroll_run
from core.normalize.schema import CanonicalPayrollRow
from product.dashboards.client_dashboard import build_client_dashboard
from product.workflow.payroll_workflow import (
    _clear_workflow_store,
    update_workflow_state,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_stores():
    _clear_runs()
    _clear_workflow_store()
    yield
    _clear_runs()
    _clear_workflow_store()


def _row(emp_id: str, gross: float, net: float, amount_impact: float = 0.0) -> CanonicalPayrollRow:
    return CanonicalPayrollRow(employee_id=emp_id, gross_pay=gross, net_pay=net)


def _finding(rule_id: str, severity: str, amount_impact: float = 0.0) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": "Test finding",
        "description": "desc",
        "evidence": {},
        "suggestion": "fix it",
        "amount_impact": amount_impact,
        "employee_refs": [],
    }


def _make_run(
    client_id: str,
    period_start: date,
    period_end: date,
    rows: list,
    findings: list = None,
    risk_score: float = 0.0,
):
    return create_payroll_run(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        dataset_hash="abc",
        normalized_rows=rows,
        risk_score=risk_score,
        findings=findings or [],
    )


# ---------------------------------------------------------------------------
# Empty client
# ---------------------------------------------------------------------------

def test_empty_client_dashboard_zero_state():
    dashboard = build_client_dashboard("unknown-client")
    assert dashboard["client_id"] == "unknown-client"
    assert dashboard["latest_run_date"] is None
    assert dashboard["latest_review_status"] is None
    assert dashboard["risk_score"] == 0.0
    assert dashboard["exposure_total"] == 0.0
    assert dashboard["employee_count"] == 0
    assert dashboard["issues_detected"] == 0
    assert dashboard["trend"] == "STABLE"


# ---------------------------------------------------------------------------
# Field accuracy
# ---------------------------------------------------------------------------

def test_dashboard_latest_run_date():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)])
    dashboard = build_client_dashboard("c1")
    assert dashboard["latest_run_date"] == "2026-01-31"


def test_dashboard_employee_count():
    rows = [_row("e1", 3000, 2500), _row("e2", 4000, 3300), _row("e3", 2800, 2300)]
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), rows)
    dashboard = build_client_dashboard("c1")
    assert dashboard["employee_count"] == 3


def test_dashboard_risk_score():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], risk_score=42.0)
    dashboard = build_client_dashboard("c1")
    assert dashboard["risk_score"] == 42.0


def test_dashboard_issues_detected():
    findings = [
        _finding("IE.PAYE.001", "HIGH"),
        _finding("IE.USC.001", "MEDIUM"),
    ]
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], findings=findings)
    dashboard = build_client_dashboard("c1")
    assert dashboard["issues_detected"] == 2


def test_dashboard_exposure_total_from_findings():
    findings = [
        _finding("IE.PAYE.001", "HIGH", amount_impact=500.0),
        _finding("IE.USC.001", "MEDIUM", amount_impact=150.0),
    ]
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], findings=findings)
    dashboard = build_client_dashboard("c1")
    assert dashboard["exposure_total"] == 650.0


def test_dashboard_exposure_zero_when_no_findings():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)])
    dashboard = build_client_dashboard("c1")
    assert dashboard["exposure_total"] == 0.0


# ---------------------------------------------------------------------------
# Latest run is the most recent period_end
# ---------------------------------------------------------------------------

def test_dashboard_reflects_latest_run_not_first():
    _make_run("c1", date(2025, 12, 1), date(2025, 12, 31), [_row("e1", 3000, 2500)], risk_score=10.0)
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 4000, 3300), _row("e2", 5000, 4000)], risk_score=20.0)
    dashboard = build_client_dashboard("c1")
    assert dashboard["latest_run_date"] == "2026-01-31"
    assert dashboard["employee_count"] == 2
    assert dashboard["risk_score"] == 20.0


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------

def test_dashboard_trend_stable_single_run():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], risk_score=10.0)
    dashboard = build_client_dashboard("c1")
    assert dashboard["trend"] == "STABLE"


def test_dashboard_trend_increasing():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], risk_score=10.0)
    _make_run("c1", date(2026, 2, 1), date(2026, 2, 28), [_row("e1", 3000, 2500)], risk_score=30.0)
    _make_run("c1", date(2026, 3, 1), date(2026, 3, 31), [_row("e1", 3000, 2500)], risk_score=60.0)
    dashboard = build_client_dashboard("c1")
    assert dashboard["trend"] == "INCREASING"


def test_dashboard_trend_decreasing():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], risk_score=60.0)
    _make_run("c1", date(2026, 2, 1), date(2026, 2, 28), [_row("e1", 3000, 2500)], risk_score=30.0)
    _make_run("c1", date(2026, 3, 1), date(2026, 3, 31), [_row("e1", 3000, 2500)], risk_score=10.0)
    dashboard = build_client_dashboard("c1")
    assert dashboard["trend"] == "DECREASING"


# ---------------------------------------------------------------------------
# latest_review_status from workflow layer
# ---------------------------------------------------------------------------

def test_dashboard_review_status_from_workflow():
    run = _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)])
    update_workflow_state(
        {"review_decision": {"status": "APPROVED"}},
        run_id=run.run_id,
        client_id="c1",
    )
    dashboard = build_client_dashboard("c1")
    assert dashboard["latest_review_status"] == "SAFE_TO_SUBMIT"


def test_dashboard_review_status_review_required():
    run = _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)])
    update_workflow_state(
        {"review_decision": {"status": "REQUIRES_REVIEW"}},
        run_id=run.run_id,
        client_id="c1",
    )
    dashboard = build_client_dashboard("c1")
    assert dashboard["latest_review_status"] == "REVIEW_REQUIRED"


def test_dashboard_review_status_defaults_to_reviewing_when_no_workflow():
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)])
    dashboard = build_client_dashboard("c1")
    assert dashboard["latest_review_status"] == "REVIEWING"


# ---------------------------------------------------------------------------
# Multi-client isolation
# ---------------------------------------------------------------------------

def test_multi_client_isolation():
    _make_run("client-A", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], risk_score=5.0)
    _make_run("client-B", date(2026, 1, 1), date(2026, 1, 31), [_row("e2", 5000, 4200), _row("e3", 6000, 5000)], risk_score=80.0)

    dash_a = build_client_dashboard("client-A")
    dash_b = build_client_dashboard("client-B")

    assert dash_a["client_id"] == "client-A"
    assert dash_a["employee_count"] == 1
    assert dash_a["risk_score"] == 5.0

    assert dash_b["client_id"] == "client-B"
    assert dash_b["employee_count"] == 2
    assert dash_b["risk_score"] == 80.0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_deterministic_output():
    findings = [_finding("IE.PAYE.001", "HIGH", amount_impact=250.0)]
    _make_run("c1", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)], findings=findings, risk_score=10.0)
    dash1 = build_client_dashboard("c1")
    dash2 = build_client_dashboard("c1")
    assert dash1 == dash2


def test_client_id_in_output_matches_input():
    _make_run("MY-CLIENT-99", date(2026, 1, 1), date(2026, 1, 31), [_row("e1", 3000, 2500)])
    dashboard = build_client_dashboard("MY-CLIENT-99")
    assert dashboard["client_id"] == "MY-CLIENT-99"
