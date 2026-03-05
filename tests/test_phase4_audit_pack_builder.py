"""Phase 4 Gate 5: tests for core.reporting.audit_pack_builder."""
import json
import pytest
from core.reporting.bureau_summary import BureauSummary
from core.reporting.exposure_engine import ExposureReport
from core.reporting.audit_pack_builder import build_audit_pack


def _summary() -> BureauSummary:
    return BureauSummary(
        run_id="run-1",
        ruleset_version="IE-2026.01",
        verification_status="CLEAN",
        underpayment_total=0.0,
        overpayment_total=0.0,
        employees_impacted=0,
        confidence_level="HIGH",
    )


def _exposure() -> ExposureReport:
    return ExposureReport(
        underpayment_total=0.0,
        overpayment_total=0.0,
        categories=[],
        employees_impacted=0,
        quantifiable_findings=0,
        non_quantifiable_findings=0,
        confidence_level="HIGH",
    )


def test_audit_pack_shape():
    """Pack has exactly the five required keys; values are bytes."""
    pack = build_audit_pack(
        _summary(),
        _exposure(),
        [],
        "IE-2026.01",
        "abc123",
    )
    assert set(pack.keys()) == {
        "summary.json",
        "exposure_breakdown.json",
        "findings.json",
        "rules_version.txt",
        "input_hash.txt",
    }
    for k, v in pack.items():
        assert isinstance(v, bytes), f"{k} value must be bytes"


def test_summary_json_shape():
    """summary.json decodes to JSON with bureau summary fields."""
    pack = build_audit_pack(_summary(), _exposure(), [], "v1", "h1")
    data = json.loads(pack["summary.json"].decode("utf-8"))
    assert data["run_id"] == "run-1"
    assert data["ruleset_version"] == "IE-2026.01"
    assert data["verification_status"] == "CLEAN"
    assert data["underpayment_total"] == 0.0
    assert data["overpayment_total"] == 0.0
    assert data["employees_impacted"] == 0
    assert data["confidence_level"] == "HIGH"


def test_exposure_breakdown_json_shape():
    """exposure_breakdown.json has underpayment_total, overpayment_total, categories."""
    report = ExposureReport(
        underpayment_total=10.0,
        overpayment_total=5.0,
        categories=[],
        employees_impacted=2,
        quantifiable_findings=1,
        non_quantifiable_findings=0,
        confidence_level="MEDIUM",
    )
    pack = build_audit_pack(
        _summary(),
        report,
        [],
        "v1",
        "h1",
    )
    data = json.loads(pack["exposure_breakdown.json"].decode("utf-8"))
    assert data["underpayment_total"] == 10.0
    assert data["overpayment_total"] == 5.0
    assert data["categories"] == []
    assert data["employees_impacted"] == 2
    assert data["confidence_level"] == "MEDIUM"


def test_findings_json_and_txt_files():
    """findings.json is array; rules_version.txt and input_hash.txt are plain text."""
    findings = [{"rule_id": "R1", "title": "T", "description": "D", "severity": "HIGH"}]
    pack = build_audit_pack(_summary(), _exposure(), findings, "IE-2026.01", "deadbeef")
    findings_data = json.loads(pack["findings.json"].decode("utf-8"))
    assert isinstance(findings_data, list)
    assert len(findings_data) == 1
    assert findings_data[0]["rule_id"] == "R1"
    assert pack["rules_version.txt"].decode("utf-8") == "IE-2026.01"
    assert pack["input_hash.txt"].decode("utf-8") == "deadbeef"


def test_stable_json_output():
    """Same inputs produce identical byte output."""
    findings = [
        {"rule_id": "B", "title": "T2", "description": "", "severity": "LOW"},
        {"rule_id": "A", "title": "T1", "description": "", "severity": "HIGH"},
    ]
    pack1 = build_audit_pack(_summary(), _exposure(), findings, "v1", "h1")
    pack2 = build_audit_pack(_summary(), _exposure(), findings, "v1", "h1")
    assert pack1["summary.json"] == pack2["summary.json"]
    assert pack1["exposure_breakdown.json"] == pack2["exposure_breakdown.json"]
    assert pack1["findings.json"] == pack2["findings.json"]
    assert pack1["rules_version.txt"] == pack2["rules_version.txt"]
    assert pack1["input_hash.txt"] == pack2["input_hash.txt"]


def test_findings_sorted_stably():
    """Findings in JSON are in deterministic order (by rule_id, title, etc.)."""
    findings = [
        {"rule_id": "R2", "title": "B", "description": "", "severity": "LOW"},
        {"rule_id": "R1", "title": "A", "description": "", "severity": "HIGH"},
    ]
    pack = build_audit_pack(_summary(), _exposure(), findings, "v1", "h1")
    data = json.loads(pack["findings.json"].decode("utf-8"))
    assert data[0]["rule_id"] == "R1"
    assert data[1]["rule_id"] == "R2"
