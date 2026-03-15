"""
Phase 7: Full pipeline integration tests.

Covers the complete payroll compliance pipeline using real modules and a
realistic 3-row Irish payroll fixture — no mocks, no stubs.

Pipeline stages exercised:
  1. Ingest   : load_table()               → raw DataFrame
  2. Normalize: normalize()                → (rows, invalid_rows)
  3. Rules    : run_all() + load_ie_config → findings list
  4. Scoring  : score_bundle()             → risk/compliance bundle
  5. Summary  : aggregate_severity_summary → counts by severity
  6. Reporting: build_pdf()               → PDF file on disk
  7. Replay   : all deterministic outputs → identical on second run

Fixture: tests/fixtures/pipeline_payroll.csv
  E001 — clean row (no violations)
  E002 — zero PAYE with taxable gross > 0  → IE.PAYE.003 HIGH
  E003 — PRSI-ee exceeds 4% of gross       → IE.PRSI.002 HIGH
          USC present but gross < threshold → IE.USC.001  LOW
          PRSI-ee > 0 but gross < threshold → IE.PRSI.001 LOW

Expected bundle:
  risk_points=22, compliance_score=78, risk_band="MEDIUM_RISK",
  exposure_total=0, severity HIGH=2, MEDIUM=0, LOW=2, TOTAL=4
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from apps.api.helpers import aggregate_severity_summary
from apps.api.schemas import Finding, RunOut
from core.ingest.loader import load_table
from core.normalize.mapper import normalize
from core.reporting.pdf import build_pdf
from core.rules.engine import load_ie_config, run_all
from core.scoring.risk import score_bundle
from core.security.crypto import sha256_of_text

# ---------------------------------------------------------------------------
# Fixture paths and mapping
# ---------------------------------------------------------------------------

_FIXTURE_CSV = Path(__file__).parent / "fixtures" / "pipeline_payroll.csv"

# Identity mapping: CSV column names already match canonical field names.
_PIPELINE_MAPPING: Dict[str, str] = {
    "employee_id": "employee_id",
    "gross_pay": "gross_pay",
    "net_pay": "net_pay",
    "paye": "paye",
    "usc": "usc",
    "prsi_ee": "prsi_ee",
    "prsi_er": "prsi_er",
    "pension_ee": "pension_ee",
    "pay_date": "pay_date",
}

# ---------------------------------------------------------------------------
# Expected outputs (derived by tracing all 30 rules against fixture data)
# ---------------------------------------------------------------------------

_EXPECTED_VALID_ROWS = 3
_EXPECTED_INVALID_ROWS = 0

_EXPECTED_FINDINGS = [
    {"rule_id": "IE.PAYE.003", "severity": "HIGH", "employee_refs": ["E002"]},
    {"rule_id": "IE.PRSI.002", "severity": "HIGH", "employee_refs": ["E003"]},
    {"rule_id": "IE.USC.001",  "severity": "LOW",  "employee_refs": ["E003"]},
    {"rule_id": "IE.PRSI.001", "severity": "LOW",  "employee_refs": ["E003"]},
]

_EXPECTED_RISK_POINTS = 22
_EXPECTED_COMPLIANCE_SCORE = 78
_EXPECTED_RISK_BAND = "MEDIUM_RISK"
_EXPECTED_EXPOSURE_TOTAL = 0

_EXPECTED_SEVERITY_SUMMARY = {"HIGH": 2, "MEDIUM": 0, "LOW": 2, "TOTAL": 4}

# ---------------------------------------------------------------------------
# Module-level pipeline run (shared for performance; all tests read-only)
# ---------------------------------------------------------------------------


def _run_pipeline() -> Tuple[List[Any], List[dict], List[dict], Dict, Dict]:
    """Execute the full pipeline and return all intermediate outputs."""
    df = load_table(str(_FIXTURE_CSV))
    rows, invalid_rows = normalize(df, _PIPELINE_MAPPING)
    cfg = load_ie_config()
    findings = run_all(rows, cfg)
    bundle = score_bundle(findings)
    severity_summary = aggregate_severity_summary(findings)
    return rows, invalid_rows, findings, bundle, severity_summary


# Run once at module load; tests share the result.
_rows, _invalid_rows, _findings, _bundle, _severity_summary = _run_pipeline()

# ---------------------------------------------------------------------------
# Stage 1: Ingest
# ---------------------------------------------------------------------------


def test_fixture_csv_exists():
    assert _FIXTURE_CSV.exists(), f"Fixture not found: {_FIXTURE_CSV}"


def test_load_table_returns_dataframe():
    """load_table() must return a non-None object with len() support."""
    df = load_table(str(_FIXTURE_CSV))
    assert df is not None
    assert len(df) == _EXPECTED_VALID_ROWS


def test_load_table_has_required_columns():
    """Raw DataFrame must contain the expected column set."""
    df = load_table(str(_FIXTURE_CSV))
    required = {"employee_id", "gross_pay", "net_pay"}
    assert required.issubset(set(df.columns))


def test_load_table_has_correct_row_count():
    df = load_table(str(_FIXTURE_CSV))
    assert len(df) == 3


# ---------------------------------------------------------------------------
# Stage 2: Normalize
# ---------------------------------------------------------------------------


def test_normalize_produces_correct_valid_row_count():
    assert len(_rows) == _EXPECTED_VALID_ROWS


def test_normalize_produces_zero_invalid_rows():
    assert len(_invalid_rows) == _EXPECTED_INVALID_ROWS


def test_normalized_rows_have_canonical_employee_ids():
    ids = {r.employee_id for r in _rows}
    assert ids == {"E001", "E002", "E003"}


def test_normalized_rows_have_numeric_gross_pay():
    for row in _rows:
        assert isinstance(row.gross_pay, float)
        assert row.gross_pay > 0


def test_normalized_row_e001_gross_pay():
    row = next(r for r in _rows if r.employee_id == "E001")
    assert row.gross_pay == pytest.approx(2000.00)


def test_normalized_row_e002_zero_paye():
    row = next(r for r in _rows if r.employee_id == "E002")
    assert row.paye == pytest.approx(0.00)


def test_normalized_row_e003_prsi_ee():
    row = next(r for r in _rows if r.employee_id == "E003")
    assert row.prsi_ee == pytest.approx(100.00)


def test_normalized_rows_all_have_pay_date():
    for row in _rows:
        assert row.pay_date is not None


# ---------------------------------------------------------------------------
# Stage 3: Rule findings
# ---------------------------------------------------------------------------


def test_findings_count_is_correct():
    assert len(_findings) == len(_EXPECTED_FINDINGS)


def test_findings_rule_ids_match_expected():
    expected_ids = [e["rule_id"] for e in _EXPECTED_FINDINGS]
    actual_ids = [f["rule_id"] for f in _findings]
    assert actual_ids == expected_ids


def test_findings_severities_match_expected():
    expected_sevs = [e["severity"] for e in _EXPECTED_FINDINGS]
    actual_sevs = [f["severity"] for f in _findings]
    assert actual_sevs == expected_sevs


def test_findings_employee_refs_match_expected():
    expected_refs = [e["employee_refs"] for e in _EXPECTED_FINDINGS]
    actual_refs = [f["employee_refs"] for f in _findings]
    assert actual_refs == expected_refs


def test_findings_ie_paye_003_targets_e002():
    paye_findings = [f for f in _findings if f["rule_id"] == "IE.PAYE.003"]
    assert len(paye_findings) == 1
    assert paye_findings[0]["employee_refs"] == ["E002"]
    assert paye_findings[0]["severity"] == "HIGH"


def test_findings_ie_prsi_002_targets_e003():
    prsi_findings = [f for f in _findings if f["rule_id"] == "IE.PRSI.002"]
    assert len(prsi_findings) == 1
    assert prsi_findings[0]["employee_refs"] == ["E003"]
    assert prsi_findings[0]["severity"] == "HIGH"


def test_findings_ie_usc_001_targets_e003():
    usc_findings = [f for f in _findings if f["rule_id"] == "IE.USC.001"]
    assert len(usc_findings) == 1
    assert usc_findings[0]["employee_refs"] == ["E003"]
    assert usc_findings[0]["severity"] == "LOW"


def test_findings_ie_prsi_001_targets_e003():
    prsi_001 = [f for f in _findings if f["rule_id"] == "IE.PRSI.001"]
    assert len(prsi_001) == 1
    assert prsi_001[0]["employee_refs"] == ["E003"]
    assert prsi_001[0]["severity"] == "LOW"


def test_findings_no_violations_for_e001():
    e001_findings = [f for f in _findings if "E001" in f.get("employee_refs", [])]
    assert e001_findings == []


def test_findings_all_have_required_keys():
    required = {"rule_id", "severity", "title", "description", "evidence", "suggestion",
                "amount_impact", "employee_refs"}
    for f in _findings:
        assert required.issubset(set(f.keys())), f"Finding {f['rule_id']} missing keys"


def test_findings_severities_are_valid():
    for f in _findings:
        assert f["severity"] in {"HIGH", "MEDIUM", "LOW"}


def test_findings_evidence_is_dict():
    for f in _findings:
        assert isinstance(f["evidence"], dict)


def test_findings_employee_refs_are_lists():
    for f in _findings:
        assert isinstance(f["employee_refs"], list)
        assert len(f["employee_refs"]) >= 1


# ---------------------------------------------------------------------------
# Stage 4: Scoring
# ---------------------------------------------------------------------------


def test_bundle_risk_points():
    assert _bundle["risk_points"] == _EXPECTED_RISK_POINTS


def test_bundle_compliance_score():
    assert _bundle["compliance_score"] == _EXPECTED_COMPLIANCE_SCORE


def test_bundle_risk_band():
    assert _bundle["risk_band"] == _EXPECTED_RISK_BAND


def test_bundle_exposure_total():
    assert _bundle["exposure_total"] == _EXPECTED_EXPOSURE_TOTAL


def test_bundle_has_required_keys():
    required = {"risk_points", "compliance_score", "risk_band", "exposure_total",
                "counts_by_severity", "counts_by_rule", "total_findings"}
    assert required.issubset(set(_bundle.keys()))


def test_bundle_total_findings():
    assert _bundle["total_findings"] == len(_EXPECTED_FINDINGS)


def test_bundle_counts_by_severity_high():
    assert _bundle["counts_by_severity"]["HIGH"] == 2


def test_bundle_counts_by_severity_medium():
    assert _bundle["counts_by_severity"]["MEDIUM"] == 0


def test_bundle_counts_by_severity_low():
    assert _bundle["counts_by_severity"]["LOW"] == 2


def test_bundle_counts_by_rule_contains_all_fired_rules():
    assert "IE.PAYE.003" in _bundle["counts_by_rule"]
    assert "IE.PRSI.002" in _bundle["counts_by_rule"]
    assert "IE.USC.001" in _bundle["counts_by_rule"]
    assert "IE.PRSI.001" in _bundle["counts_by_rule"]


def test_bundle_compliance_score_in_valid_range():
    assert 0 <= _bundle["compliance_score"] <= 100


# ---------------------------------------------------------------------------
# Stage 5: Severity summary
# ---------------------------------------------------------------------------


def test_severity_summary_high():
    assert _severity_summary["HIGH"] == _EXPECTED_SEVERITY_SUMMARY["HIGH"]


def test_severity_summary_medium():
    assert _severity_summary["MEDIUM"] == _EXPECTED_SEVERITY_SUMMARY["MEDIUM"]


def test_severity_summary_low():
    assert _severity_summary["LOW"] == _EXPECTED_SEVERITY_SUMMARY["LOW"]


def test_severity_summary_total():
    assert _severity_summary["TOTAL"] == _EXPECTED_SEVERITY_SUMMARY["TOTAL"]


def test_severity_summary_keys_are_stable():
    assert set(_severity_summary.keys()) == {"HIGH", "MEDIUM", "LOW", "TOTAL"}


def test_severity_summary_total_equals_finding_count():
    assert _severity_summary["TOTAL"] == len(_findings)


# ---------------------------------------------------------------------------
# Stage 6: PDF reporting
# ---------------------------------------------------------------------------


def test_build_pdf_creates_file(tmp_path):
    pdf_path = str(tmp_path / "pipeline_run.pdf")
    build_pdf(
        pdf_path,
        company="Integration Corp",
        ruleset_version="IE-2026.01",
        risk_score=_bundle["compliance_score"],
        findings=_findings,
        severity_summary=_severity_summary,
        exposure_total=_bundle["exposure_total"],
        risk_band=_bundle["risk_band"],
    )
    assert Path(pdf_path).exists()


def test_build_pdf_file_is_nonempty(tmp_path):
    pdf_path = str(tmp_path / "pipeline_run.pdf")
    build_pdf(
        pdf_path,
        company="Integration Corp",
        ruleset_version="IE-2026.01",
        risk_score=_bundle["compliance_score"],
        findings=_findings,
        severity_summary=_severity_summary,
        exposure_total=_bundle["exposure_total"],
        risk_band=_bundle["risk_band"],
    )
    assert os.path.getsize(pdf_path) > 0


def test_build_pdf_has_pdf_magic_bytes(tmp_path):
    pdf_path = str(tmp_path / "pipeline_run.pdf")
    build_pdf(
        pdf_path,
        company="Integration Corp",
        ruleset_version="IE-2026.01",
        risk_score=_bundle["compliance_score"],
        findings=_findings,
    )
    with open(pdf_path, "rb") as fh:
        header = fh.read(4)
    assert header == b"%PDF"


def test_build_pdf_stable_file_size_across_two_calls(tmp_path):
    """Identical inputs must produce identical file sizes (timestamp is fixed-width)."""
    kwargs = dict(
        company="Integration Corp",
        ruleset_version="IE-2026.01",
        risk_score=_bundle["compliance_score"],
        findings=_findings,
        severity_summary=_severity_summary,
        exposure_total=_bundle["exposure_total"],
        risk_band=_bundle["risk_band"],
    )
    p1 = str(tmp_path / "r1.pdf")
    p2 = str(tmp_path / "r2.pdf")
    build_pdf(p1, **kwargs)
    build_pdf(p2, **kwargs)
    assert os.path.getsize(p1) == os.path.getsize(p2)


# ---------------------------------------------------------------------------
# Stage 7: Deterministic replay
# ---------------------------------------------------------------------------


def test_pipeline_replay_findings_identical():
    """Running the pipeline twice must produce the same findings list."""
    _, _, findings2, _, _ = _run_pipeline()
    assert _findings == findings2


def test_pipeline_replay_bundle_identical():
    """Running the pipeline twice must produce the same score bundle."""
    _, _, _, bundle2, _ = _run_pipeline()
    assert _bundle == bundle2


def test_pipeline_replay_severity_summary_identical():
    """Running the pipeline twice must produce the same severity summary."""
    _, _, _, _, sv2 = _run_pipeline()
    assert _severity_summary == sv2


def test_pipeline_replay_risk_points_stable():
    _, _, findings2, bundle2, _ = _run_pipeline()
    assert bundle2["risk_points"] == _EXPECTED_RISK_POINTS


def test_pipeline_replay_compliance_score_stable():
    _, _, findings2, bundle2, _ = _run_pipeline()
    assert bundle2["compliance_score"] == _EXPECTED_COMPLIANCE_SCORE


def test_pipeline_replay_risk_band_stable():
    _, _, findings2, bundle2, _ = _run_pipeline()
    assert bundle2["risk_band"] == _EXPECTED_RISK_BAND


def test_pipeline_replay_findings_order_stable():
    """Rule ordering must be deterministic: findings appear in same sequence."""
    _, _, findings2, _, _ = _run_pipeline()
    ids1 = [f["rule_id"] for f in _findings]
    ids2 = [f["rule_id"] for f in findings2]
    assert ids1 == ids2


# ---------------------------------------------------------------------------
# Integration: findings_json DB payload from pipeline
# ---------------------------------------------------------------------------


def test_findings_json_payload_is_valid_json():
    payload = json.dumps({"score_bundle": _bundle, "findings": _findings}, sort_keys=True)
    parsed = json.loads(payload)
    assert isinstance(parsed, dict)


def test_findings_json_payload_has_required_keys():
    payload = json.loads(
        json.dumps({"score_bundle": _bundle, "findings": _findings}, sort_keys=True)
    )
    assert "score_bundle" in payload
    assert "findings" in payload


def test_findings_json_payload_is_deterministic():
    j1 = json.dumps({"score_bundle": _bundle, "findings": _findings}, sort_keys=True)
    j2 = json.dumps({"score_bundle": _bundle, "findings": _findings}, sort_keys=True)
    assert j1 == j2


def test_findings_json_findings_count_matches_pipeline():
    payload = json.loads(
        json.dumps({"score_bundle": _bundle, "findings": _findings}, sort_keys=True)
    )
    assert len(payload["findings"]) == len(_EXPECTED_FINDINGS)


def test_findings_json_score_bundle_matches_pipeline():
    payload = json.loads(
        json.dumps({"score_bundle": _bundle, "findings": _findings}, sort_keys=True)
    )
    assert payload["score_bundle"]["risk_points"] == _EXPECTED_RISK_POINTS
    assert payload["score_bundle"]["compliance_score"] == _EXPECTED_COMPLIANCE_SCORE
    assert payload["score_bundle"]["risk_band"] == _EXPECTED_RISK_BAND


# ---------------------------------------------------------------------------
# Integration: RunOut schema from pipeline outputs
# ---------------------------------------------------------------------------


def _make_run_out(**overrides):
    """Helper: construct a RunOut from pipeline outputs with findings_hash."""
    defaults = dict(
        id=1,
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings=[Finding(**f) for f in _findings],
        counts={"total": len(_rows), "valid": len(_rows), "invalid": 0},
        invalid_rows=[],
        risk_points=_bundle["risk_points"],
        compliance_score=_bundle["compliance_score"],
        severity_summary=_severity_summary,
        findings_hash=sha256_of_text(json.dumps(_findings, sort_keys=True)),
    )
    defaults.update(overrides)
    return RunOut(**defaults)


def test_runout_constructed_from_pipeline():
    run = _make_run_out()
    data = run.model_dump()
    assert data["risk_points"] == _EXPECTED_RISK_POINTS
    assert data["compliance_score"] == _EXPECTED_COMPLIANCE_SCORE
    assert data["severity_summary"]["TOTAL"] == 4


def test_runout_findings_are_finding_objects():
    run = _make_run_out()
    assert all(isinstance(f, Finding) for f in run.findings)
    assert len(run.findings) == len(_EXPECTED_FINDINGS)


def test_runout_findings_hash_is_present():
    """RunOut must expose a non-empty findings_hash string."""
    run = _make_run_out()
    assert isinstance(run.findings_hash, str)
    assert len(run.findings_hash) == 64  # SHA256 hex = 64 chars


def test_runout_findings_hash_is_deterministic():
    """Same findings must produce the same hash in RunOut on repeated construction."""
    run1 = _make_run_out()
    run2 = _make_run_out()
    assert run1.findings_hash == run2.findings_hash
