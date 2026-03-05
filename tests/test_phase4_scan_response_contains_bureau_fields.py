"""Phase 4 Gate 6: scan response contains bureau fields; backward compatibility for summary."""
import re
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

# Same small CSV as existing scan endpoint test
SCAN_CSV = b"employee_id,gross_pay,net_pay\nE1,1000.0,800.0\nE2,2000.0,1600.0\n"

HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def test_scan_response_contains_new_keys():
    """Response contains run_id, input_hash, bureau_summary, exposure_breakdown."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "input_hash" in data
    assert "bureau_summary" in data
    assert "exposure_breakdown" in data


def test_bureau_summary_verification_status_exists():
    """bureau_summary.verification_status exists."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    data = response.json()
    assert "bureau_summary" in data
    assert "verification_status" in data["bureau_summary"]


def test_input_hash_64_hex_chars():
    """input_hash looks like 64 hex chars (lowercase sha256)."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    data = response.json()
    assert "input_hash" in data
    assert HEX_64.match(data["input_hash"]), "input_hash must be 64 lowercase hex chars"


def test_existing_summary_key_still_exists():
    """Existing 'summary' key still exists and is unchanged in shape."""
    response = client.post(
        "/scan/",
        files={"file": ("payroll.csv", SCAN_CSV, "text/csv")},
    )
    data = response.json()
    assert "summary" in data
    summary = data["summary"]
    assert "total_findings" in summary
    assert "critical" in summary
    assert "warning" in summary
    assert "info" in summary
    assert "overall" in summary
    assert summary["overall"] in ("RED", "AMBER", "GREEN")
