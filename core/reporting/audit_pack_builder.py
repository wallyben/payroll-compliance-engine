"""Phase 4 Gate 5: Audit pack as dict of bytes. No file writes. Stable JSON."""
from __future__ import annotations
import json
from dataclasses import asdict
from typing import Any

from core.reporting.bureau_summary import BureauSummary
from core.reporting.exposure_engine import ExposureReport


def _summary_to_dict(s: BureauSummary) -> dict[str, Any]:
    return asdict(s)


def _exposure_to_dict(r: ExposureReport) -> dict[str, Any]:
    return {
        "underpayment_total": r.underpayment_total,
        "overpayment_total": r.overpayment_total,
        "categories": [asdict(c) for c in r.categories],
        "employees_impacted": r.employees_impacted,
        "quantifiable_findings": r.quantifiable_findings,
        "non_quantifiable_findings": r.non_quantifiable_findings,
        "confidence_level": r.confidence_level,
    }


def _findings_sort_key(f: dict[str, Any]) -> tuple:
    """Stable sort key for findings list."""
    return (
        f.get("rule_id") or "",
        f.get("title") or "",
        f.get("description") or "",
        json.dumps(f.get("evidence") or {}, sort_keys=True),
    )


def build_audit_pack(
    bureau_summary: BureauSummary,
    exposure_report: ExposureReport,
    findings: list[dict[str, Any]],
    ruleset_version: str,
    input_hash: str,
) -> dict[str, bytes]:
    """Build audit pack: dict of filename -> UTF-8 bytes. No file writes. Stable JSON."""
    summary_dict = _summary_to_dict(bureau_summary)
    summary_bytes = json.dumps(summary_dict, sort_keys=True, indent=2).encode("utf-8")

    exposure_dict = _exposure_to_dict(exposure_report)
    exposure_bytes = json.dumps(exposure_dict, sort_keys=True, indent=2).encode("utf-8")

    sorted_findings = sorted(findings, key=_findings_sort_key)
    findings_bytes = json.dumps(sorted_findings, sort_keys=True, indent=2).encode("utf-8")

    rules_version_bytes = ruleset_version.encode("utf-8")
    input_hash_bytes = input_hash.encode("utf-8")

    return {
        "summary.json": summary_bytes,
        "exposure_breakdown.json": exposure_bytes,
        "findings.json": findings_bytes,
        "rules_version.txt": rules_version_bytes,
        "input_hash.txt": input_hash_bytes,
    }
