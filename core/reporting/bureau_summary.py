"""Phase 4 Gate 4: Bureau summary from run, exposure, and certificate. Deterministic."""
from __future__ import annotations
from dataclasses import dataclass

from core.reporting.exposure_engine import ExposureReport
from core.reporting.certificate_builder import CertificateData


@dataclass
class BureauSummary:
    run_id: str
    ruleset_version: str
    verification_status: str
    underpayment_total: float
    overpayment_total: float
    employees_impacted: int
    confidence_level: str


def build_bureau_summary(
    run_id: str,
    ruleset_version: str,
    exposure_report: ExposureReport,
    certificate: CertificateData,
) -> BureauSummary:
    """Build deterministic bureau summary from exposure report and certificate."""
    return BureauSummary(
        run_id=run_id,
        ruleset_version=ruleset_version,
        verification_status=certificate.verification_status,
        underpayment_total=exposure_report.underpayment_total,
        overpayment_total=exposure_report.overpayment_total,
        employees_impacted=exposure_report.employees_impacted,
        confidence_level=exposure_report.confidence_level,
    )
