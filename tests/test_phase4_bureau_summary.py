"""Phase 4 Gate 4: tests for core.reporting.bureau_summary."""
import pytest
from core.reporting.exposure_engine import ExposureReport
from core.reporting.certificate_builder import CertificateData
from core.reporting.bureau_summary import BureauSummary, build_bureau_summary


def _exposure(under: float = 0.0, over: float = 0.0, employees: int = 0, confidence: str = "HIGH") -> ExposureReport:
    return ExposureReport(
        underpayment_total=under,
        overpayment_total=over,
        categories=[],
        employees_impacted=employees,
        quantifiable_findings=0,
        non_quantifiable_findings=0,
        confidence_level=confidence,
    )


def test_bureau_summary_shape():
    """BureauSummary has required fields populated from exposure and certificate."""
    report = _exposure(under=100.0, over=50.0, employees=5, confidence="MEDIUM")
    cert = CertificateData(
        verification_status="EXPOSURE_IDENTIFIED",
        statement="",
        limitation="",
    )
    summary = build_bureau_summary("run-123", "IE-2026.01", report, cert)
    assert summary.run_id == "run-123"
    assert summary.ruleset_version == "IE-2026.01"
    assert summary.verification_status == "EXPOSURE_IDENTIFIED"
    assert summary.underpayment_total == 100.0
    assert summary.overpayment_total == 50.0
    assert summary.employees_impacted == 5
    assert summary.confidence_level == "MEDIUM"


def test_bureau_summary_clean():
    """Clean run: verification_status from certificate, zero exposure."""
    report = _exposure(0.0, 0.0, 0, "HIGH")
    cert = CertificateData(verification_status="CLEAN", statement="", limitation="")
    summary = build_bureau_summary("r1", "IE-2026.01", report, cert)
    assert summary.verification_status == "CLEAN"
    assert summary.underpayment_total == 0.0
    assert summary.overpayment_total == 0.0
    assert summary.employees_impacted == 0
    assert summary.confidence_level == "HIGH"


def test_deterministic_output():
    """Same inputs produce identical summary every time."""
    report = _exposure(10.5, 2.0, 3, "LOW")
    cert = CertificateData(verification_status="EXPOSURE_IDENTIFIED", statement="", limitation="")
    first = build_bureau_summary("id", "v1", report, cert)
    for _ in range(5):
        again = build_bureau_summary("id", "v1", report, cert)
        assert again.run_id == first.run_id
        assert again.ruleset_version == first.ruleset_version
        assert again.verification_status == first.verification_status
        assert again.underpayment_total == first.underpayment_total
        assert again.overpayment_total == first.overpayment_total
        assert again.employees_impacted == first.employees_impacted
        assert again.confidence_level == first.confidence_level
