"""
core/reporting/evidence_pack.py
---------------------------------
Audit-ready compliance evidence pack generator.

Consolidates all scan pipeline outputs into a single structured package
suitable for regulatory audit, client delivery, and evidence archiving.

Inputs consumed (all already-computed; nothing is re-derived):
  - RunOut object (from the API pipeline)
  - core.reporting.exposure_engine.quantify_exposure()  output
  - core.reporting.certificate.generate_certificate()   output
  - core.reporting.bureau_summary.generate_bureau_summary() output

Does NOT modify the rule engine, scoring logic, or any upstream module.

Output top-level keys
    scan_metadata      – provenance: engine version, rules version, timestamp, hashes
    validation_summary – rules checked, violations, per-severity counts
    exposure_analysis  – financial exposure total and impacted employee count
    certificate        – full certificate dict (embedded verbatim)
    bureau_summary     – full bureau summary dict (embedded verbatim)
    findings           – findings list exactly as produced by the rule engine
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Canonical severity keys produced by core/rules
_KNOWN_SEVERITIES: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")


def build_evidence_pack(
    run_out: Any,
    exposure_result: Dict[str, Any],
    certificate_result: Dict[str, Any],
    bureau_summary_result: Dict[str, Any],
    dataset_hash: str = "",
) -> Dict[str, Any]:
    """Build an audit-ready compliance evidence pack.

    Parameters
    ----------
    run_out:
        RunOut-compatible dict or Pydantic RunOut instance.
        Fields consumed:
          - findings          List    rule findings (dict or Pydantic Finding)
          - findings_hash     str     SHA-256 integrity hash
          - ruleset_version   str     rules config version
          - severity_summary  dict    pre-computed severity counts (optional)

    exposure_result:
        Output of ``core.reporting.exposure_engine.quantify_exposure()``.
        Fields consumed: exposure_total, employees_impacted.

    certificate_result:
        Output of ``core.reporting.certificate.generate_certificate()``.
        Fields consumed: engine_version, rules_version, scan_date,
        findings_hash, rules_checked, violations_found.
        Embedded verbatim under "certificate".

    bureau_summary_result:
        Output of ``core.reporting.bureau_summary.generate_bureau_summary()``.
        Embedded verbatim under "bureau_summary".

    dataset_hash:
        SHA-256 hash of the original uploaded payroll dataset.
        Supplied by the pipeline orchestrator; not derivable from findings.
        Defaults to empty string if the caller does not provide it.

    Returns
    -------
    {
        "scan_metadata": {
            "engine_version": str,   from certificate
            "rules_version":  str,   from certificate (run_out fallback)
            "scan_timestamp": str,   from certificate.scan_date
            "dataset_hash":   str,   as supplied
            "findings_hash":  str,   from certificate (run_out fallback)
        },
        "validation_summary": {
            "rules_checked":    int,
            "violations_found": int,
            "severity_summary": {"HIGH": int, "MEDIUM": int, "LOW": int},
        },
        "exposure_analysis": {
            "exposure_total":     float,
            "employees_impacted": int,
        },
        "certificate":    dict,        full certificate_result
        "bureau_summary": dict,        full bureau_summary_result
        "findings":       List[dict],  findings exactly as produced by rule engine
    }

    Output is fully deterministic: identical inputs always produce identical
    outputs.  No randomness is introduced at any stage.  Finding order is
    preserved from the rule engine; no re-sorting is applied.
    """
    findings_raw: List[Any] = _get(run_out, "findings", default=[])
    findings: List[Dict[str, Any]] = [_to_dict(f) for f in findings_raw]

    # findings_hash: certificate is authoritative; fall back to run_out
    findings_hash: str = (
        certificate_result.get("findings_hash")
        or _get(run_out, "findings_hash", default="")
    )

    # rules_version: certificate carries it; fall back to run_out.ruleset_version
    rules_version: str = (
        certificate_result.get("rules_version")
        or _get(run_out, "ruleset_version", default="")
    )

    return {
        "scan_metadata": {
            "engine_version": certificate_result.get("engine_version", ""),
            "rules_version":  rules_version,
            "scan_timestamp": certificate_result.get("scan_date", ""),
            "dataset_hash":   dataset_hash,
            "findings_hash":  findings_hash,
        },
        "validation_summary": {
            "rules_checked":    certificate_result.get("rules_checked", 0),
            "violations_found": certificate_result.get("violations_found", 0),
            "severity_summary": _severity_summary(run_out, findings),
        },
        "exposure_analysis": {
            "exposure_total":     exposure_result.get("exposure_total", 0.0),
            "employees_impacted": exposure_result.get("employees_impacted", 0),
        },
        "certificate":    certificate_result,
        "bureau_summary": bureau_summary_result,
        "findings":       findings,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _severity_summary(
    run_out: Any,
    findings: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Return per-severity finding counts.

    Preference order:
      1. run_out.severity_summary  (pre-computed by the pipeline; most efficient)
      2. Derived from the serialised findings list                (fallback)

    Only the three canonical severity keys (HIGH, MEDIUM, LOW) are returned,
    ensuring a stable, predictable structure regardless of input.
    """
    existing: Optional[dict] = _get(run_out, "severity_summary")
    if isinstance(existing, dict) and existing:
        extracted = {k: int(existing[k]) for k in _KNOWN_SEVERITIES if k in existing}
        if extracted:
            return {k: extracted.get(k, 0) for k in _KNOWN_SEVERITIES}

    # Derive from findings
    counts: Dict[str, int] = {k: 0 for k in _KNOWN_SEVERITIES}
    for f in findings:
        sev: str = f.get("severity", "")
        if sev in counts:
            counts[sev] += 1
    return counts


def _to_dict(finding: Any) -> Dict[str, Any]:
    """Convert a finding to a plain dict, preserving all fields verbatim."""
    if isinstance(finding, dict):
        return finding
    if hasattr(finding, "model_dump"):          # Pydantic v2
        return finding.model_dump()
    if hasattr(finding, "dict"):                # Pydantic v1
        return finding.dict()
    return dict(vars(finding))                  # fallback


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve a field from a dict or a Pydantic-style attribute object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    value = getattr(obj, key, default)
    return value if value is not None else default
