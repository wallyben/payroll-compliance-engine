"""Phase 4 Gate 3: tests for core.reporting.certificate_builder."""
import pytest
from core.reporting.exposure_engine import ExposureReport
from core.reporting.certificate_builder import (
    CertificateData,
    VerificationStatus,
    build_certificate,
    STATEMENT_CLEAN,
    STATEMENT_EXPOSURE,
    LIMITATION,
)


def _report(under: float = 0.0, over: float = 0.0) -> ExposureReport:
    return ExposureReport(
        underpayment_total=under,
        overpayment_total=over,
        categories=[],
        employees_impacted=0,
        quantifiable_findings=0,
        non_quantifiable_findings=0,
        confidence_level="HIGH",
    )


def test_clean_zero_findings():
    """No findings, zero under/over => CLEAN."""
    report = _report(0.0, 0.0)
    cert = build_certificate(report, [])
    assert cert.verification_status == VerificationStatus.CLEAN.value
    assert cert.statement == STATEMENT_CLEAN
    assert cert.limitation == LIMITATION


def test_clean_non_critical_findings():
    """Zero under/over and only LOW/MEDIUM findings => CLEAN."""
    report = _report(0.0, 0.0)
    findings = [
        {"rule_id": "R1", "severity": "LOW", "title": "T", "description": "", "employee_refs": []},
        {"rule_id": "R2", "severity": "MEDIUM", "title": "T", "description": "", "employee_refs": []},
    ]
    cert = build_certificate(report, findings)
    assert cert.verification_status == VerificationStatus.CLEAN.value
    assert cert.statement == STATEMENT_CLEAN
    assert cert.limitation == LIMITATION


def test_exposure_non_zero_under():
    """Non-zero underpayment => EXPOSURE_IDENTIFIED."""
    report = _report(100.0, 0.0)
    cert = build_certificate(report, [])
    assert cert.verification_status == VerificationStatus.EXPOSURE_IDENTIFIED.value
    assert cert.statement == STATEMENT_EXPOSURE
    assert cert.limitation == LIMITATION


def test_exposure_non_zero_over():
    """Non-zero overpayment => EXPOSURE_IDENTIFIED."""
    report = _report(0.0, 50.0)
    cert = build_certificate(report, [])
    assert cert.verification_status == VerificationStatus.EXPOSURE_IDENTIFIED.value
    assert cert.statement == STATEMENT_EXPOSURE


def test_exposure_critical_finding():
    """Zero under/over but HIGH severity finding => EXPOSURE_IDENTIFIED."""
    report = _report(0.0, 0.0)
    findings = [
        {"rule_id": "R1", "severity": "HIGH", "title": "T", "description": "", "employee_refs": []},
    ]
    cert = build_certificate(report, findings)
    assert cert.verification_status == VerificationStatus.EXPOSURE_IDENTIFIED.value
    assert cert.statement == STATEMENT_EXPOSURE
    assert cert.limitation == LIMITATION


def test_limitation_always_included():
    """Limitation is always present for both statuses."""
    cert_clean = build_certificate(_report(0.0, 0.0), [])
    cert_exp = build_certificate(_report(1.0, 0.0), [])
    assert cert_clean.limitation == LIMITATION
    assert cert_exp.limitation == LIMITATION
    assert "legal advice" in cert_clean.limitation
