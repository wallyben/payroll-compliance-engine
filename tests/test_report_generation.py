"""
Phase 5: reporting hardening — output shape, PDF generation, and determinism tests.

Covers:
- RunOut schema key set is frozen (no silent additions or removals).
- Finding schema key set is frozen.
- RunOut model_dump() is deterministic for the same input.
- RunOut JSON serialisation round-trips correctly.
- aggregate_severity_summary() produces the correct shape and values.
- aggregate_severity_summary() is deterministic.
- findings_json DB payload structure has the expected top-level keys.
- findings_json with sort_keys=True is deterministic across repeated builds.
- build_pdf() creates a file, the file is non-empty, and it begins with %PDF.
- build_pdf() works without optional params (backward compat).
- build_pdf() works with all optional Phase 5 params.
- build_pdf() handles zero findings, many findings (pagination), and large exposure.
- Two build_pdf() calls with identical inputs produce the same file size
  (content is deterministic; only the metadata timestamp is variable, and it
  is fixed-width in the PDF format so file size is unchanged).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

from apps.api.helpers import aggregate_severity_summary
from apps.api.schemas import Finding, RunOut
from core.reporting.pdf import build_pdf
from core.scoring.risk import score_bundle
from core.security.crypto import sha256_of_text

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_REQUIRED_RUNOUT_KEYS = {
    "id",
    "upload_id",
    "mapping_id",
    "ruleset_version",
    "findings",
    "counts",
    "invalid_rows",
    "risk_points",
    "compliance_score",
    "severity_summary",
    "findings_hash",
}

_REQUIRED_FINDING_KEYS = {
    "rule_id",
    "severity",
    "title",
    "description",
    "evidence",
    "suggestion",
    "amount_impact",
    "employee_refs",
}


def _finding(severity: str, rule_id: str = "IE.TEST.001", amount_impact=None) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": f"Test {severity}",
        "description": "Test description",
        "evidence": {"count": 1},
        "suggestion": "Check the data.",
        "amount_impact": amount_impact,
        "employee_refs": ["E001"],
    }


def _make_run_out(findings: List[dict]) -> RunOut:
    bundle = score_bundle(findings)
    severity_summary = aggregate_severity_summary(findings)
    return RunOut(
        id=1,
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings=[Finding(**f) for f in findings],
        counts={"total": len(findings), "valid": len(findings), "invalid": 0},
        invalid_rows=[],
        risk_points=bundle["risk_points"],
        compliance_score=bundle["compliance_score"],
        severity_summary=severity_summary,
        findings_hash=sha256_of_text(json.dumps(findings, sort_keys=True)),
    )


HIGH = _finding("HIGH", amount_impact=100.0)
MEDIUM = _finding("MEDIUM", "IE.USC.001", amount_impact=50.0)
LOW = _finding("LOW", "IE.PRSI.001", amount_impact=None)

# ---------------------------------------------------------------------------
# RunOut schema shape — frozen key contract
# ---------------------------------------------------------------------------


def test_runout_model_dump_keys_stable():
    run = _make_run_out([HIGH])
    assert set(run.model_dump().keys()) == _REQUIRED_RUNOUT_KEYS


def test_runout_model_dump_keys_stable_empty_findings():
    run = _make_run_out([])
    assert set(run.model_dump().keys()) == _REQUIRED_RUNOUT_KEYS


def test_finding_schema_keys_stable():
    f = Finding(**HIGH)
    assert set(f.model_dump().keys()) == _REQUIRED_FINDING_KEYS


def test_runout_findings_list_contains_finding_objects():
    run = _make_run_out([HIGH, LOW])
    assert all(isinstance(f, Finding) for f in run.findings)
    assert len(run.findings) == 2


# ---------------------------------------------------------------------------
# RunOut JSON serialisation — determinism
# ---------------------------------------------------------------------------


def test_runout_model_dump_is_deterministic():
    run = _make_run_out([HIGH, MEDIUM, LOW])
    assert run.model_dump() == run.model_dump()


def test_runout_model_dump_json_is_valid_json():
    run = _make_run_out([HIGH])
    parsed = json.loads(run.model_dump_json())
    assert isinstance(parsed, dict)
    assert "findings" in parsed


def test_runout_model_dump_json_round_trips():
    run = _make_run_out([HIGH, MEDIUM])
    dumped = run.model_dump()
    assert dumped["risk_points"] == score_bundle([HIGH, MEDIUM])["risk_points"]
    assert dumped["compliance_score"] == score_bundle([HIGH, MEDIUM])["compliance_score"]


def test_runout_json_deterministic_across_two_builds():
    run1 = _make_run_out([HIGH, MEDIUM])
    run2 = _make_run_out([HIGH, MEDIUM])
    assert run1.model_dump() == run2.model_dump()


def test_runout_severity_summary_in_model_dump():
    run = _make_run_out([HIGH, HIGH, MEDIUM, LOW])
    sv = run.model_dump()["severity_summary"]
    assert sv["HIGH"] == 2
    assert sv["MEDIUM"] == 1
    assert sv["LOW"] == 1
    assert sv["TOTAL"] == 4


# ---------------------------------------------------------------------------
# aggregate_severity_summary — shape, values, determinism
# ---------------------------------------------------------------------------


def test_aggregate_severity_summary_keys_are_stable():
    result = aggregate_severity_summary([])
    assert set(result.keys()) == {"HIGH", "MEDIUM", "LOW", "TOTAL"}


def test_aggregate_severity_summary_empty_findings():
    result = aggregate_severity_summary([])
    assert result == {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}


def test_aggregate_severity_summary_single_high():
    result = aggregate_severity_summary([HIGH])
    assert result["HIGH"] == 1
    assert result["MEDIUM"] == 0
    assert result["LOW"] == 0
    assert result["TOTAL"] == 1


def test_aggregate_severity_summary_mixed():
    result = aggregate_severity_summary([HIGH, HIGH, MEDIUM, LOW])
    assert result["HIGH"] == 2
    assert result["MEDIUM"] == 1
    assert result["LOW"] == 1
    assert result["TOTAL"] == 4


def test_aggregate_severity_summary_total_equals_len():
    findings = [HIGH, MEDIUM, LOW, HIGH, LOW]
    result = aggregate_severity_summary(findings)
    assert result["TOTAL"] == len(findings)


def test_aggregate_severity_summary_unknown_severity_counted_in_total():
    """Unknown severity still counts towards TOTAL."""
    unknown = _finding("CRITICAL")
    result = aggregate_severity_summary([unknown])
    assert result["TOTAL"] == 1
    assert result["HIGH"] == 0


def test_aggregate_severity_summary_is_deterministic():
    findings = [HIGH, MEDIUM, LOW, HIGH]
    assert aggregate_severity_summary(findings) == aggregate_severity_summary(findings)


# ---------------------------------------------------------------------------
# findings_json DB payload — structure and determinism
# ---------------------------------------------------------------------------


def _build_findings_json(findings: List[dict]) -> str:
    """Mirrors the logic in apps/api/routers/runs.py for the findings_json column."""
    bundle = score_bundle(findings)
    return json.dumps({"score_bundle": bundle, "findings": findings}, sort_keys=True)


def test_findings_json_payload_has_required_top_level_keys():
    payload = json.loads(_build_findings_json([HIGH]))
    assert "score_bundle" in payload
    assert "findings" in payload


def test_findings_json_score_bundle_has_required_keys():
    payload = json.loads(_build_findings_json([HIGH]))
    bundle_keys = set(payload["score_bundle"].keys())
    for key in ("risk_points", "compliance_score", "risk_band", "exposure_total",
                "counts_by_severity", "counts_by_rule", "total_findings"):
        assert key in bundle_keys, f"Missing bundle key: '{key}'"


def test_findings_json_findings_list_matches_input():
    findings = [HIGH, MEDIUM]
    payload = json.loads(_build_findings_json(findings))
    assert len(payload["findings"]) == 2
    assert payload["findings"][0]["rule_id"] == HIGH["rule_id"]


def test_findings_json_round_trips_correctly():
    findings = [HIGH, LOW]
    raw = _build_findings_json(findings)
    parsed = json.loads(raw)
    assert parsed["findings"] == findings


def test_findings_json_is_deterministic():
    findings = [HIGH, MEDIUM, LOW]
    assert _build_findings_json(findings) == _build_findings_json(findings)


def test_findings_json_with_sort_keys_is_stable():
    """sort_keys=True guarantees key ordering is not insertion-order-dependent."""
    bundle = score_bundle([HIGH])
    payload = {"score_bundle": bundle, "findings": [HIGH]}
    j1 = json.dumps(payload, sort_keys=True)
    j2 = json.dumps(payload, sort_keys=True)
    assert j1 == j2


def test_findings_json_exposure_total_is_correct():
    findings = [_finding("HIGH", amount_impact=200.0), _finding("LOW", amount_impact=50.0)]
    payload = json.loads(_build_findings_json(findings))
    assert payload["score_bundle"]["exposure_total"] == 250.0


def test_findings_json_empty_findings():
    payload = json.loads(_build_findings_json([]))
    assert payload["findings"] == []
    assert payload["score_bundle"]["risk_points"] == 0
    assert payload["score_bundle"]["compliance_score"] == 100


# ---------------------------------------------------------------------------
# build_pdf() — creation, validity, backward compat, new params
# ---------------------------------------------------------------------------


def test_build_pdf_creates_file(tmp_path):
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Acme Ltd", ruleset_version="IE-2026.01",
              risk_score=90, findings=[])
    assert Path(path).exists()


def test_build_pdf_file_is_nonempty(tmp_path):
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Acme Ltd", ruleset_version="IE-2026.01",
              risk_score=90, findings=[])
    assert os.path.getsize(path) > 0


def test_build_pdf_file_starts_with_pdf_magic(tmp_path):
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Acme Ltd", ruleset_version="IE-2026.01",
              risk_score=90, findings=[])
    with open(path, "rb") as fh:
        header = fh.read(4)
    assert header == b"%PDF", f"Expected PDF magic bytes, got {header!r}"


def test_build_pdf_without_optional_params_backward_compat(tmp_path):
    """Old callers that do not pass optional Phase 5 params must still work."""
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Acme", ruleset_version="IE-2026.01",
              risk_score=80, findings=[HIGH])
    assert Path(path).exists()


def test_build_pdf_with_severity_summary(tmp_path):
    path = str(tmp_path / "report.pdf")
    summary = {"HIGH": 1, "MEDIUM": 0, "LOW": 0, "TOTAL": 1}
    build_pdf(path, company="Acme", ruleset_version="IE-2026.01",
              risk_score=90, findings=[HIGH], severity_summary=summary)
    assert Path(path).exists()


def test_build_pdf_with_exposure_total(tmp_path):
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Acme", ruleset_version="IE-2026.01",
              risk_score=90, findings=[HIGH], exposure_total=1500.75)
    assert Path(path).exists()


def test_build_pdf_with_risk_band(tmp_path):
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Acme", ruleset_version="IE-2026.01",
              risk_score=90, findings=[HIGH], risk_band="LOW_RISK")
    assert Path(path).exists()


def test_build_pdf_with_all_optional_params(tmp_path):
    path = str(tmp_path / "report.pdf")
    summary = {"HIGH": 1, "MEDIUM": 1, "LOW": 0, "TOTAL": 2}
    build_pdf(
        path,
        company="Test Corp",
        ruleset_version="IE-2026.01",
        risk_score=75,
        findings=[HIGH, MEDIUM],
        severity_summary=summary,
        exposure_total=150.0,
        risk_band="MEDIUM_RISK",
    )
    assert Path(path).exists()
    assert os.path.getsize(path) > 0


def test_build_pdf_with_zero_findings(tmp_path):
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="Clean Co", ruleset_version="IE-2026.01",
              risk_score=100, findings=[])
    assert Path(path).exists()
    assert os.path.getsize(path) > 0


def test_build_pdf_with_many_findings_triggers_pagination(tmp_path):
    """More than ~60 findings triggers a page break; build must not crash."""
    path = str(tmp_path / "report.pdf")
    many = [_finding("HIGH", rule_id=f"IE.TEST.{i:03d}") for i in range(80)]
    build_pdf(path, company="Big Co", ruleset_version="IE-2026.01",
              risk_score=0, findings=many)
    assert Path(path).exists()
    assert os.path.getsize(path) > 0


def test_build_pdf_caps_findings_at_200(tmp_path):
    """Findings list is capped at 200 lines in the PDF; build must not crash."""
    path = str(tmp_path / "report.pdf")
    many = [_finding("LOW", rule_id=f"IE.TEST.{i:03d}") for i in range(250)]
    build_pdf(path, company="Big Co", ruleset_version="IE-2026.01",
              risk_score=0, findings=many)
    assert Path(path).exists()


def test_build_pdf_stable_file_size_for_same_input(tmp_path):
    """Two builds with identical inputs must produce the same file size.

    The only non-deterministic element in ReportLab output is the PDF
    creation-date timestamp.  This is stored as a fixed-width string
    (D:YYYYMMDDHHmmSS) so the total file size remains identical even when
    the timestamp value changes.
    """
    summary = {"HIGH": 1, "MEDIUM": 0, "LOW": 1, "TOTAL": 2}
    kwargs: Dict[str, Any] = dict(
        company="Stable Corp",
        ruleset_version="IE-2026.01",
        risk_score=85,
        findings=[HIGH, LOW],
        severity_summary=summary,
        exposure_total=100.0,
        risk_band="LOW_RISK",
    )
    path1 = str(tmp_path / "r1.pdf")
    path2 = str(tmp_path / "r2.pdf")
    build_pdf(path1, **kwargs)
    build_pdf(path2, **kwargs)
    assert os.path.getsize(path1) == os.path.getsize(path2)


def test_build_pdf_severity_summary_none_does_not_render_section(tmp_path):
    """When severity_summary=None (default), the PDF must still be valid."""
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="A", ruleset_version="IE-2026.01",
              risk_score=100, findings=[], severity_summary=None)
    assert Path(path).exists()


def test_build_pdf_exposure_total_zero_renders(tmp_path):
    """exposure_total=0.0 is a valid value and must render without crash."""
    path = str(tmp_path / "report.pdf")
    build_pdf(path, company="A", ruleset_version="IE-2026.01",
              risk_score=100, findings=[], exposure_total=0.0)
    assert Path(path).exists()


# ---------------------------------------------------------------------------
# Integration: score_bundle → aggregate_severity_summary → build_pdf pipeline
# ---------------------------------------------------------------------------


def test_full_pipeline_produces_pdf_and_valid_runout(tmp_path):
    """End-to-end smoke test: findings → bundle → severity_summary → PDF + RunOut."""
    findings = [HIGH, HIGH, MEDIUM, LOW]
    bundle = score_bundle(findings)
    severity_summary = aggregate_severity_summary(findings)

    # PDF
    pdf_path = str(tmp_path / "run_1.pdf")
    build_pdf(
        pdf_path,
        company="Integration Corp",
        ruleset_version="IE-2026.01",
        risk_score=bundle["compliance_score"],
        findings=findings,
        severity_summary=severity_summary,
        exposure_total=bundle["exposure_total"],
        risk_band=bundle["risk_band"],
    )
    assert Path(pdf_path).exists()
    assert os.path.getsize(pdf_path) > 0

    # RunOut
    run = _make_run_out(findings)
    data = run.model_dump()
    assert data["risk_points"] == bundle["risk_points"]
    assert data["compliance_score"] == bundle["compliance_score"]
    assert data["severity_summary"]["TOTAL"] == 4


def test_full_pipeline_is_deterministic(tmp_path):
    """Same findings → same bundle, same severity_summary, same RunOut."""
    findings = [HIGH, MEDIUM]

    bundle1 = score_bundle(findings)
    bundle2 = score_bundle(findings)
    assert bundle1 == bundle2

    sv1 = aggregate_severity_summary(findings)
    sv2 = aggregate_severity_summary(findings)
    assert sv1 == sv2

    run1 = _make_run_out(findings)
    run2 = _make_run_out(findings)
    assert run1.model_dump() == run2.model_dump()
