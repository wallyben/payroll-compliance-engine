"""Minimal integration test for POST /scan. Uses real engine, no mocks."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

# Small CSV with required columns: employee_id, gross_pay, net_pay
SCAN_CSV = b"employee_id,gross_pay,net_pay\nE1,1000.0,800.0\nE2,2000.0,1600.0\n"


def test_scan_upload_returns_200_and_summary():
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    summary = data["summary"]
    assert "total_findings" in summary
    assert "critical" in summary
    assert "warning" in summary
    assert "info" in summary
    assert "overall" in summary
    assert summary["overall"] in ("RED", "AMBER", "GREEN")
    assert "auto_enrolment_findings" in data
    assert "revenue_findings" in data
    assert "all_findings" in data
