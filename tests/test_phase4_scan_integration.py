"""Phase 4 Gate 6: scan endpoint returns bureau_summary, exposure_breakdown, run_id, input_hash."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

SCAN_CSV = b"employee_id,gross_pay,net_pay\nE1,1000.0,800.0\nE2,2000.0,1600.0\n"


def test_scan_response_includes_phase4_keys():
    """POST /scan response includes run_id, input_hash, bureau_summary, exposure_breakdown."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "run_id" in data
    assert "input_hash" in data
    assert "bureau_summary" in data
    assert "exposure_breakdown" in data


def test_bureau_summary_shape():
    """bureau_summary has required fields."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    data = response.json()
    bs = data["bureau_summary"]
    assert "run_id" in bs
    assert "ruleset_version" in bs
    assert "verification_status" in bs
    assert "underpayment_total" in bs
    assert "overpayment_total" in bs
    assert "employees_impacted" in bs
    assert "confidence_level" in bs
    assert bs["verification_status"] in ("CLEAN", "EXPOSURE_IDENTIFIED")


def test_exposure_breakdown_shape():
    """exposure_breakdown has underpayment_total, overpayment_total, categories."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    data = response.json()
    exp = data["exposure_breakdown"]
    assert "underpayment_total" in exp
    assert "overpayment_total" in exp
    assert "categories" in exp
    assert "employees_impacted" in exp
    assert "confidence_level" in exp


def test_deterministic_input_hash():
    """Same CSV upload yields same input_hash (run_id is UUID per request)."""
    r1 = client.post("/scan/", files={"file": ("a.csv", SCAN_CSV, "text/csv")})
    r2 = client.post("/scan/", files={"file": ("b.csv", SCAN_CSV, "text/csv")})
    assert r1.status_code == 200 and r2.status_code == 200
    d1, d2 = r1.json(), r2.json()
    assert d1["input_hash"] == d2["input_hash"]
    assert len(d1["run_id"]) > 0
