"""Phase 4 Gate 3: Certificate data from exposure and findings. Deterministic, no randomness."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.reporting.exposure_engine import ExposureReport


class VerificationStatus(str, Enum):
    CLEAN = "CLEAN"
    EXPOSURE_IDENTIFIED = "EXPOSURE_IDENTIFIED"


STATEMENT_CLEAN = (
    "Based on deterministic validation against the specified ruleset, no statutory payroll "
    "calculation irregularities were detected within the scope of the applied rule library."
)
STATEMENT_EXPOSURE = (
    "Deterministic validation identified statutory payroll calculation irregularities within "
    "the applied ruleset. Quantified exposure is detailed in the accompanying summary."
)
LIMITATION = (
    "This validation is limited to deterministic rule-based analysis of the supplied payroll "
    "dataset and does not constitute legal advice."
)


@dataclass
class CertificateData:
    verification_status: str
    statement: str
    limitation: str


def _has_critical_findings(findings: list[dict[str, Any]]) -> bool:
    """Critical = CRITICAL or HIGH severity."""
    for f in findings:
        sev = (f.get("severity") or "").upper()
        if sev in ("CRITICAL", "HIGH"):
            return True
    return False


def build_certificate(exposure_report: ExposureReport, findings: list[dict[str, Any]]) -> CertificateData:
    """Build certificate: CLEAN iff zero under/over and no critical findings; else EXPOSURE_IDENTIFIED."""
    under = exposure_report.underpayment_total
    over = exposure_report.overpayment_total
    critical = _has_critical_findings(findings)
    if under == 0 and over == 0 and not critical:
        status = VerificationStatus.CLEAN
        statement = STATEMENT_CLEAN
    else:
        status = VerificationStatus.EXPOSURE_IDENTIFIED
        statement = STATEMENT_EXPOSURE
    return CertificateData(
        verification_status=status.value,
        statement=statement,
        limitation=LIMITATION,
    )
