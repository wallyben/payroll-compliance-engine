"""
core/reporting/bureau_summary.py
----------------------------------
Bureau-facing one-page compliance summary generator.

Consumes already-computed outputs from:
  - RunOut object (produced by the API pipeline)
  - core.reporting.exposure_engine.quantify_exposure()
  - core.reporting.certificate.generate_certificate()

Does NOT modify the engine pipeline, rule engine, or scoring logic.

Confidence levels
    HIGH   — no findings of any kind (payroll fully clean)
    MEDIUM — findings present but none are HIGH or CRITICAL severity
    LOW    — one or more HIGH or CRITICAL severity findings
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_HIGH_SEVERITIES: frozenset[str] = frozenset({"HIGH", "CRITICAL"})


def generate_bureau_summary(
    run_out: Any,
    exposure_result: Dict[str, Any],
    certificate_result: Dict[str, Any],
    employees_scanned: int,
) -> Dict[str, Any]:
    """Generate a bureau-facing compliance summary.

    Parameters
    ----------
    run_out:
        RunOut-compatible dict or Pydantic RunOut instance.
        Fields consumed:
          - findings          List   rule findings
          - compliance_score  float  0-100 score (used as risk_score)
          - findings_hash     str    integrity hash (fallback if absent from cert)

    exposure_result:
        Output of ``core.reporting.exposure_engine.quantify_exposure()``.
        Fields consumed:
          - exposure_total    float

    certificate_result:
        Output of ``core.reporting.certificate.generate_certificate()``.
        Fields consumed:
          - validation_status  str
          - rules_checked      int
          - violations_found   int
          - findings_hash      str

    employees_scanned:
        Total number of employees in the payroll run.  Supplied by the
        caller who owns the payroll dataset; not derivable from findings
        alone (clean employees leave no findings).

    Returns
    -------
    {
        "validation_status": str    "PASSED" or "FAILED"
        "risk_score":        int    compliance_score from run_out (0-100)
        "exposure_total":    float  total financial exposure
        "employees_scanned": int    as supplied
        "rules_checked":     int    total rules evaluated
        "violations_found":  int    count of HIGH / CRITICAL findings
        "findings_hash":     str    SHA-256 integrity hash
        "confidence":        str    "HIGH" | "MEDIUM" | "LOW"
    }

    Output is fully deterministic: identical inputs always produce identical
    outputs.  No randomness is introduced at any stage.
    """
    findings: List[Any] = _get(run_out, "findings", default=[])

    # compliance_score is 0-100 float; surface as integer risk_score
    raw_score = _get(run_out, "compliance_score", default=0)
    risk_score: int = int(raw_score) if raw_score is not None else 0

    # findings_hash: prefer the certificate's copy (already validated);
    # fall back to run_out in case certificate was generated without one
    findings_hash: str = (
        certificate_result.get("findings_hash")
        or _get(run_out, "findings_hash", default="")
    )

    return {
        "validation_status": certificate_result.get("validation_status", "UNKNOWN"),
        "risk_score": risk_score,
        "exposure_total": exposure_result.get("exposure_total", 0.0),
        "employees_scanned": employees_scanned,
        "rules_checked": certificate_result.get("rules_checked", 0),
        "violations_found": certificate_result.get("violations_found", 0),
        "findings_hash": findings_hash,
        "confidence": _confidence(findings),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _confidence(findings: List[Any]) -> str:
    """Derive confidence level from a findings list.

    HIGH   — no findings at all
    MEDIUM — findings present, none HIGH or CRITICAL
    LOW    — any HIGH or CRITICAL finding present
    """
    if not findings:
        return "HIGH"
    if any(_sev(f) in _HIGH_SEVERITIES for f in findings):
        return "LOW"
    return "MEDIUM"


def _sev(finding: Any) -> str:
    """Extract severity from a finding dict or Pydantic Finding model."""
    if isinstance(finding, dict):
        return finding.get("severity", "")
    return getattr(finding, "severity", "")


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve a field from a dict or a Pydantic-style attribute object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    value = getattr(obj, key, default)
    return value if value is not None else default
