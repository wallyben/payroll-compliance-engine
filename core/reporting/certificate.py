"""
core/reporting/certificate.py
-------------------------------
Deterministic compliance verification certificate generator.

Consumes the RunOut object already produced by the API pipeline.
Does NOT modify any rule or scoring logic.

Certificate ID derivation
    sha256(findings_hash + engine_version)

    Both inputs are stable across runs, so the certificate_id is fully
    reproducible and can be independently verified by any regulator that
    holds the same findings_hash and knows the engine version.

Validation status
    PASSED  — zero findings with severity HIGH or CRITICAL
    FAILED  — one or more findings with severity HIGH or CRITICAL
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from core.rules.engine import RULE_ORDER

# Severities that trigger FAILED status.
_FAILING_SEVERITIES: frozenset[str] = frozenset({"HIGH", "CRITICAL"})


def generate_certificate(
    run_out: Any,
    engine_version: str,
    scan_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a deterministic compliance verification certificate.

    Parameters
    ----------
    run_out:
        A RunOut-compatible dict **or** a Pydantic RunOut instance
        (serialised or not).  Expected fields consumed:
          - findings        List[dict]  rule findings from core/rules
          - findings_hash   str         SHA-256 integrity hash of findings
          - ruleset_version str         rules config version (e.g. "IE-2026.01")

    engine_version:
        Semantic version string for the compliance engine (e.g. "1.0.0").
        Included in certificate_id derivation for full auditability.

    scan_date:
        ISO-8601 date string (YYYY-MM-DD).  Pass explicitly; no server-side
        clock is consulted so that certificates remain reproducible.

    Returns
    -------
    {
        "certificate_id":    str   sha256(findings_hash + engine_version)
        "scan_date":         str   ISO-8601 date supplied by caller
        "engine_version":    str   as supplied
        "rules_version":     str   from run_out.ruleset_version
        "findings_hash":     str   from run_out.findings_hash
        "rules_checked":     int   total rules in the engine (len(RULE_ORDER))
        "violations_found":  int   count of HIGH / CRITICAL severity findings
        "validation_status": str   "PASSED" or "FAILED"
    }

    Output is fully deterministic: identical inputs always produce identical
    outputs.  No randomness is introduced at any stage.
    """
    findings: List[Dict[str, Any]] = _get(run_out, "findings", default=[])
    findings_hash: str = _get(run_out, "findings_hash", default="")
    ruleset_version: str = _get(run_out, "ruleset_version", default="")

    violations: List[Any] = [
        f for f in findings if _severity(f) in _FAILING_SEVERITIES
    ]
    violations_found: int = len(violations)
    validation_status: str = "FAILED" if violations_found > 0 else "PASSED"

    return {
        "certificate_id": _derive_id(findings_hash, engine_version),
        "scan_date": scan_date or "",
        "engine_version": engine_version,
        "rules_version": ruleset_version,
        "findings_hash": findings_hash,
        "rules_checked": len(RULE_ORDER),
        "violations_found": violations_found,
        "validation_status": validation_status,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _severity(finding: Any) -> Optional[str]:
    """Extract severity from a finding dict or a Pydantic Finding model."""
    if isinstance(finding, dict):
        return finding.get("severity")
    return getattr(finding, "severity", None)


def _derive_id(findings_hash: str, engine_version: str) -> str:
    """Deterministic certificate ID: sha256(findings_hash + engine_version)."""
    raw = (findings_hash + engine_version).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve a field from a dict or a Pydantic-style attribute object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    value = getattr(obj, key, default)
    return value if value is not None else default
