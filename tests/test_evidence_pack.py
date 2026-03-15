"""
tests/test_evidence_pack.py
-----------------------------
Unit tests for core/reporting/evidence_pack.py.

Test groups:
  1.  Clean scan          → evidence pack shows PASSED / zero violations
  2.  Violations present  → findings embedded, violations counted
  3.  Determinism         → identical input → identical output
  4.  Certificate embed   → certificate dict embedded verbatim
  5.  Exposure embed      → exposure data embedded correctly
  6.  Bureau summary embed→ bureau_summary dict embedded verbatim
  7.  scan_metadata       → all five metadata fields populated correctly
  8.  validation_summary  → rules_checked, violations_found, severity_summary
  9.  severity_summary    → derived from findings when run_out has none
  10. severity_summary    → uses run_out.severity_summary when present
  11. findings list       → preserved exactly (order, count, content)
  12. dataset_hash        → propagated as supplied; defaults to empty string
  13. Output contract     → top-level key set is fixed
  14. Integration         → round-trip with all real sub-modules
"""

import pytest

from core.reporting.evidence_pack import build_evidence_pack

# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------

FIXED_DATE = "2026-03-15"
ENGINE_VERSION = "1.0.0"
RULES_VERSION = "IE-2026.01"
FINDINGS_HASH = "abc123def456"


def _finding(severity: str, rule_id: str = "IE.PAYE.003", amount: float = 0.0) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": "Test finding",
        "description": "Test description",
        "evidence": {},
        "suggestion": "",
        "amount_impact": amount or None,
        "employee_refs": [],
    }


def _run_out(
    findings=None,
    compliance_score: float = 100.0,
    findings_hash: str = FINDINGS_HASH,
    ruleset_version: str = RULES_VERSION,
    severity_summary: dict = None,
) -> dict:
    base = {
        "id": 1,
        "upload_id": 1,
        "mapping_id": 1,
        "ruleset_version": ruleset_version,
        "findings": findings or [],
        "counts": {},
        "compliance_score": compliance_score,
        "findings_hash": findings_hash,
    }
    if severity_summary is not None:
        base["severity_summary"] = severity_summary
    return base


def _exposure(total: float = 0.0, impacted: int = 0) -> dict:
    return {
        "exposure_total": total,
        "employees_impacted": impacted,
        "exposure_by_rule": {},
    }


def _certificate(
    status: str = "PASSED",
    rules_checked: int = 29,
    violations_found: int = 0,
    findings_hash: str = FINDINGS_HASH,
    engine_version: str = ENGINE_VERSION,
    rules_version: str = RULES_VERSION,
    scan_date: str = FIXED_DATE,
) -> dict:
    return {
        "certificate_id": "cafebabe" * 8,
        "scan_date": scan_date,
        "engine_version": engine_version,
        "rules_version": rules_version,
        "findings_hash": findings_hash,
        "rules_checked": rules_checked,
        "violations_found": violations_found,
        "validation_status": status,
    }


def _bureau(
    status: str = "PASSED",
    risk_score: int = 100,
    exposure_total: float = 0.0,
    employees_scanned: int = 50,
    violations_found: int = 0,
    confidence: str = "HIGH",
    findings_hash: str = FINDINGS_HASH,
) -> dict:
    return {
        "validation_status": status,
        "risk_score": risk_score,
        "exposure_total": exposure_total,
        "employees_scanned": employees_scanned,
        "rules_checked": 29,
        "violations_found": violations_found,
        "findings_hash": findings_hash,
        "confidence": confidence,
    }


def _pack(
    run=None,
    exp=None,
    cert=None,
    bureau=None,
    dataset_hash: str = "",
):
    """Convenience wrapper with sane defaults."""
    return build_evidence_pack(
        run or _run_out(),
        exp or _exposure(),
        cert or _certificate(),
        bureau or _bureau(),
        dataset_hash=dataset_hash,
    )


# ---------------------------------------------------------------------------
# 1. Clean scan → PASSED evidence pack
# ---------------------------------------------------------------------------

class TestCleanScan:
    def test_validation_status_passed(self):
        pack = _pack()
        assert pack["bureau_summary"]["validation_status"] == "PASSED"

    def test_violations_found_zero(self):
        pack = _pack()
        assert pack["validation_summary"]["violations_found"] == 0

    def test_findings_list_empty(self):
        pack = _pack(run=_run_out(findings=[]))
        assert pack["findings"] == []

    def test_exposure_total_zero(self):
        pack = _pack(exp=_exposure(total=0.0))
        assert pack["exposure_analysis"]["exposure_total"] == 0.0

    def test_severity_summary_all_zero(self):
        pack = _pack(run=_run_out(findings=[]))
        ss = pack["validation_summary"]["severity_summary"]
        assert ss == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}


# ---------------------------------------------------------------------------
# 2. Violations present → findings in pack
# ---------------------------------------------------------------------------

class TestViolationsPack:
    def test_findings_embedded(self):
        f1 = _finding("HIGH", "IE.MINWAGE.001", 320.0)
        f2 = _finding("HIGH", "IE.MINWAGE.001", 480.0)
        run = _run_out(findings=[f1, f2])
        cert = _certificate(status="FAILED", violations_found=2)
        bureau = _bureau(status="FAILED", violations_found=2, confidence="LOW")
        pack = build_evidence_pack(run, _exposure(total=800.0, impacted=2), cert, bureau)
        assert len(pack["findings"]) == 2

    def test_violations_found_count(self):
        findings = [_finding("HIGH", f"R.{i}") for i in range(3)]
        run = _run_out(findings=findings)
        cert = _certificate(status="FAILED", violations_found=3)
        pack = build_evidence_pack(run, _exposure(), cert, _bureau())
        assert pack["validation_summary"]["violations_found"] == 3

    def test_finding_content_preserved(self):
        f = _finding("HIGH", "IE.PAYE.003", 100.0)
        run = _run_out(findings=[f])
        cert = _certificate(status="FAILED", violations_found=1)
        pack = build_evidence_pack(run, _exposure(), cert, _bureau())
        stored = pack["findings"][0]
        assert stored["rule_id"] == "IE.PAYE.003"
        assert stored["severity"] == "HIGH"

    def test_finding_order_preserved(self):
        rule_ids = ["IE.PAYE.003", "IE.MINWAGE.001", "IE.USC.006"]
        findings = [_finding("HIGH", rid) for rid in rule_ids]
        run = _run_out(findings=findings)
        cert = _certificate(status="FAILED", violations_found=3)
        pack = build_evidence_pack(run, _exposure(), cert, _bureau())
        assert [f["rule_id"] for f in pack["findings"]] == rule_ids


# ---------------------------------------------------------------------------
# 3. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_identical_inputs_produce_identical_pack(self):
        f = _finding("HIGH", "IE.MINWAGE.001", 320.0)
        run = _run_out(findings=[f], compliance_score=60.0)
        exp = _exposure(total=320.0, impacted=1)
        cert = _certificate(status="FAILED", violations_found=1)
        bureau = _bureau(status="FAILED", violations_found=1, confidence="LOW")

        p1 = build_evidence_pack(run, exp, cert, bureau, dataset_hash="dshash")
        p2 = build_evidence_pack(run, exp, cert, bureau, dataset_hash="dshash")
        assert p1 == p2

    def test_stable_across_ten_calls(self):
        run = _run_out(findings=[], compliance_score=100.0)
        packs = [
            build_evidence_pack(run, _exposure(), _certificate(), _bureau())
            for _ in range(10)
        ]
        assert all(p == packs[0] for p in packs)

    def test_inputs_not_mutated(self):
        f = _finding("HIGH")
        run = _run_out(findings=[f])
        original_hash = run["findings_hash"]
        original_len = len(run["findings"])
        build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        assert run["findings_hash"] == original_hash
        assert len(run["findings"]) == original_len


# ---------------------------------------------------------------------------
# 4. Certificate embedded correctly
# ---------------------------------------------------------------------------

class TestCertificateEmbed:
    def test_certificate_embedded_verbatim(self):
        cert = _certificate(
            status="PASSED",
            rules_checked=29,
            engine_version="2.1.0",
            findings_hash="certhash",
        )
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["certificate"] is cert

    def test_certificate_id_present(self):
        cert = _certificate()
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert "certificate_id" in pack["certificate"]

    def test_certificate_engine_version_in_metadata(self):
        cert = _certificate(engine_version="3.0.0")
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["engine_version"] == "3.0.0"

    def test_certificate_scan_date_as_scan_timestamp(self):
        cert = _certificate(scan_date="2025-06-30")
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["scan_timestamp"] == "2025-06-30"

    def test_certificate_rules_checked_in_validation_summary(self):
        cert = _certificate(rules_checked=29)
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["validation_summary"]["rules_checked"] == 29

    def test_certificate_violations_in_validation_summary(self):
        cert = _certificate(violations_found=5)
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["validation_summary"]["violations_found"] == 5

    def test_certificate_findings_hash_in_scan_metadata(self):
        cert = _certificate(findings_hash="certhash99")
        pack = build_evidence_pack(_run_out(findings_hash="runhash"), _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["findings_hash"] == "certhash99"


# ---------------------------------------------------------------------------
# 5. Exposure data embedded correctly
# ---------------------------------------------------------------------------

class TestExposureEmbed:
    def test_exposure_total_in_exposure_analysis(self):
        exp = _exposure(total=1920.0, impacted=3)
        pack = build_evidence_pack(_run_out(), exp, _certificate(), _bureau())
        assert pack["exposure_analysis"]["exposure_total"] == 1920.0

    def test_employees_impacted_in_exposure_analysis(self):
        exp = _exposure(total=0.0, impacted=7)
        pack = build_evidence_pack(_run_out(), exp, _certificate(), _bureau())
        assert pack["exposure_analysis"]["employees_impacted"] == 7

    def test_zero_exposure_preserved(self):
        pack = build_evidence_pack(_run_out(), _exposure(total=0.0), _certificate(), _bureau())
        assert pack["exposure_analysis"]["exposure_total"] == 0.0

    def test_fractional_exposure_preserved(self):
        exp = _exposure(total=3840.75)
        pack = build_evidence_pack(_run_out(), exp, _certificate(), _bureau())
        assert pack["exposure_analysis"]["exposure_total"] == 3840.75


# ---------------------------------------------------------------------------
# 6. Bureau summary embedded correctly
# ---------------------------------------------------------------------------

class TestBureauSummaryEmbed:
    def test_bureau_summary_embedded_verbatim(self):
        bureau = _bureau(
            status="FAILED",
            risk_score=40,
            exposure_total=1920.0,
            employees_scanned=114,
            confidence="LOW",
        )
        pack = build_evidence_pack(_run_out(), _exposure(), _certificate(), bureau)
        assert pack["bureau_summary"] is bureau

    def test_bureau_confidence_accessible(self):
        bureau = _bureau(confidence="MEDIUM")
        pack = build_evidence_pack(_run_out(), _exposure(), _certificate(), bureau)
        assert pack["bureau_summary"]["confidence"] == "MEDIUM"

    def test_bureau_employees_scanned_accessible(self):
        bureau = _bureau(employees_scanned=200)
        pack = build_evidence_pack(_run_out(), _exposure(), _certificate(), bureau)
        assert pack["bureau_summary"]["employees_scanned"] == 200

    def test_bureau_risk_score_accessible(self):
        bureau = _bureau(risk_score=72)
        pack = build_evidence_pack(_run_out(), _exposure(), _certificate(), bureau)
        assert pack["bureau_summary"]["risk_score"] == 72


# ---------------------------------------------------------------------------
# 7. scan_metadata
# ---------------------------------------------------------------------------

class TestScanMetadata:
    def test_all_five_metadata_fields_present(self):
        pack = _pack()
        meta = pack["scan_metadata"]
        assert set(meta.keys()) == {
            "engine_version", "rules_version", "scan_timestamp",
            "dataset_hash", "findings_hash",
        }

    def test_rules_version_from_certificate(self):
        cert = _certificate(rules_version="IE-2027.01")
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["rules_version"] == "IE-2027.01"

    def test_rules_version_fallback_to_run_out(self):
        cert = _certificate()
        cert["rules_version"] = ""
        run = _run_out(ruleset_version="IE-2025.01")
        pack = build_evidence_pack(run, _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["rules_version"] == "IE-2025.01"

    def test_dataset_hash_propagated(self):
        pack = build_evidence_pack(
            _run_out(), _exposure(), _certificate(), _bureau(),
            dataset_hash="datasetsha256hash"
        )
        assert pack["scan_metadata"]["dataset_hash"] == "datasetsha256hash"

    def test_dataset_hash_defaults_to_empty_string(self):
        pack = _pack()
        assert pack["scan_metadata"]["dataset_hash"] == ""

    def test_findings_hash_from_certificate_preferred(self):
        cert = _certificate(findings_hash="from_cert")
        run = _run_out(findings_hash="from_run")
        pack = build_evidence_pack(run, _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["findings_hash"] == "from_cert"

    def test_findings_hash_fallback_to_run_out(self):
        cert = _certificate()
        cert["findings_hash"] = ""
        run = _run_out(findings_hash="from_run_only")
        pack = build_evidence_pack(run, _exposure(), cert, _bureau())
        assert pack["scan_metadata"]["findings_hash"] == "from_run_only"


# ---------------------------------------------------------------------------
# 8. validation_summary
# ---------------------------------------------------------------------------

class TestValidationSummary:
    def test_three_validation_summary_keys(self):
        pack = _pack()
        assert set(pack["validation_summary"].keys()) == {
            "rules_checked", "violations_found", "severity_summary"
        }

    def test_rules_checked_from_certificate(self):
        cert = _certificate(rules_checked=29)
        pack = build_evidence_pack(_run_out(), _exposure(), cert, _bureau())
        assert pack["validation_summary"]["rules_checked"] == 29


# ---------------------------------------------------------------------------
# 9. severity_summary derived from findings
# ---------------------------------------------------------------------------

class TestSeveritySummaryDerived:
    def test_derived_when_no_precomputed_summary(self):
        findings = [
            _finding("HIGH"), _finding("HIGH"),
            _finding("MEDIUM"),
            _finding("LOW"), _finding("LOW"), _finding("LOW"),
        ]
        run = _run_out(findings=findings)  # no severity_summary key
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        ss = pack["validation_summary"]["severity_summary"]
        assert ss["HIGH"] == 2
        assert ss["MEDIUM"] == 1
        assert ss["LOW"] == 3

    def test_all_three_keys_always_present(self):
        run = _run_out(findings=[_finding("HIGH")])
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        ss = pack["validation_summary"]["severity_summary"]
        assert "HIGH" in ss
        assert "MEDIUM" in ss
        assert "LOW" in ss

    def test_unknown_severity_not_included(self):
        f = _finding("HIGH")
        f["severity"] = "UNKNOWN_SEVERITY"
        run = _run_out(findings=[f])
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        ss = pack["validation_summary"]["severity_summary"]
        assert "UNKNOWN_SEVERITY" not in ss


# ---------------------------------------------------------------------------
# 10. severity_summary uses run_out.severity_summary when present
# ---------------------------------------------------------------------------

class TestSeveritySummaryPrecomputed:
    def test_precomputed_summary_used(self):
        precomputed = {"HIGH": 5, "MEDIUM": 2, "LOW": 10}
        run = _run_out(
            findings=[_finding("HIGH")],  # would give HIGH=1 if derived
            severity_summary=precomputed,
        )
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        ss = pack["validation_summary"]["severity_summary"]
        assert ss["HIGH"] == 5
        assert ss["MEDIUM"] == 2
        assert ss["LOW"] == 10

    def test_precomputed_summary_ignores_extra_keys(self):
        precomputed = {"HIGH": 1, "MEDIUM": 0, "LOW": 0, "TOTAL": 1}
        run = _run_out(severity_summary=precomputed)
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        ss = pack["validation_summary"]["severity_summary"]
        assert "TOTAL" not in ss


# ---------------------------------------------------------------------------
# 11. findings list
# ---------------------------------------------------------------------------

class TestFindingsList:
    def test_empty_findings_gives_empty_list(self):
        pack = build_evidence_pack(_run_out(findings=[]), _exposure(), _certificate(), _bureau())
        assert pack["findings"] == []

    def test_finding_count_matches_run_out(self):
        findings = [_finding("LOW", f"R.{i}") for i in range(5)]
        run = _run_out(findings=findings)
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        assert len(pack["findings"]) == 5

    def test_findings_are_plain_dicts(self):
        findings = [_finding("HIGH")]
        run = _run_out(findings=findings)
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        for f in pack["findings"]:
            assert isinstance(f, dict)

    def test_pydantic_findings_serialised_to_dict(self):
        from apps.api.schemas import Finding
        pydantic_finding = Finding(
            rule_id="IE.MINWAGE.001",
            severity="HIGH",
            title="Min wage",
            description="Below minimum wage",
        )
        run = {
            "id": 1, "upload_id": 1, "mapping_id": 1,
            "ruleset_version": RULES_VERSION,
            "findings": [pydantic_finding],
            "counts": {},
            "compliance_score": 60.0,
            "findings_hash": FINDINGS_HASH,
        }
        pack = build_evidence_pack(run, _exposure(), _certificate(), _bureau())
        assert isinstance(pack["findings"][0], dict)
        assert pack["findings"][0]["rule_id"] == "IE.MINWAGE.001"


# ---------------------------------------------------------------------------
# 12. dataset_hash
# ---------------------------------------------------------------------------

class TestDatasetHash:
    def test_dataset_hash_empty_string_by_default(self):
        pack = _pack()
        assert pack["scan_metadata"]["dataset_hash"] == ""

    def test_dataset_hash_propagated_exactly(self):
        dh = "f4a2b3c1" * 8
        pack = build_evidence_pack(
            _run_out(), _exposure(), _certificate(), _bureau(), dataset_hash=dh
        )
        assert pack["scan_metadata"]["dataset_hash"] == dh

    def test_different_dataset_hashes_produce_different_packs(self):
        p1 = build_evidence_pack(
            _run_out(), _exposure(), _certificate(), _bureau(), dataset_hash="hash_a"
        )
        p2 = build_evidence_pack(
            _run_out(), _exposure(), _certificate(), _bureau(), dataset_hash="hash_b"
        )
        assert p1["scan_metadata"]["dataset_hash"] != p2["scan_metadata"]["dataset_hash"]


# ---------------------------------------------------------------------------
# 13. Output contract
# ---------------------------------------------------------------------------

class TestOutputContract:
    def test_top_level_keys(self):
        pack = _pack()
        assert set(pack.keys()) == {
            "scan_metadata",
            "validation_summary",
            "exposure_analysis",
            "certificate",
            "bureau_summary",
            "findings",
        }

    def test_exposure_analysis_keys(self):
        pack = _pack()
        assert set(pack["exposure_analysis"].keys()) == {
            "exposure_total", "employees_impacted"
        }

    def test_scan_metadata_keys(self):
        pack = _pack()
        assert set(pack["scan_metadata"].keys()) == {
            "engine_version", "rules_version", "scan_timestamp",
            "dataset_hash", "findings_hash",
        }

    def test_validation_summary_keys(self):
        pack = _pack()
        assert set(pack["validation_summary"].keys()) == {
            "rules_checked", "violations_found", "severity_summary"
        }

    def test_severity_summary_keys(self):
        pack = _pack()
        assert set(pack["validation_summary"]["severity_summary"].keys()) == {
            "HIGH", "MEDIUM", "LOW"
        }


# ---------------------------------------------------------------------------
# 14. Integration — round-trip with all real sub-modules
# ---------------------------------------------------------------------------

class TestIntegration:
    def _make_inputs(self, findings, compliance_score, employees, fhash, dataset_hash=""):
        from core.reporting.exposure_engine import quantify_exposure
        from core.reporting.certificate import generate_certificate
        from core.reporting.bureau_summary import generate_bureau_summary

        run = _run_out(
            findings=findings,
            compliance_score=compliance_score,
            findings_hash=fhash,
        )
        exp = quantify_exposure(findings)
        cert = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        bureau = generate_bureau_summary(run, exp, cert, employees)
        return run, exp, cert, bureau

    def test_clean_run_full_pipeline(self):
        run, exp, cert, bureau = self._make_inputs([], 100.0, 50, "cleanhash")
        pack = build_evidence_pack(run, exp, cert, bureau)

        assert pack["bureau_summary"]["validation_status"] == "PASSED"
        assert pack["bureau_summary"]["confidence"] == "HIGH"
        assert pack["validation_summary"]["violations_found"] == 0
        assert pack["exposure_analysis"]["exposure_total"] == 0.0
        assert pack["findings"] == []
        assert pack["scan_metadata"]["engine_version"] == ENGINE_VERSION
        assert pack["scan_metadata"]["rules_version"] == RULES_VERSION

    def test_violations_full_pipeline(self):
        findings = [
            {
                "rule_id": "IE.MINWAGE.001", "severity": "HIGH",
                "title": "Min wage", "description": "Below min",
                "evidence": {}, "suggestion": "",
                "amount_impact": 320.0, "employee_refs": ["E101"],
            },
            {
                "rule_id": "IE.MINWAGE.001", "severity": "HIGH",
                "title": "Min wage", "description": "Below min",
                "evidence": {}, "suggestion": "",
                "amount_impact": 480.0, "employee_refs": ["E102"],
            },
            {
                "rule_id": "IE.USC.006", "severity": "LOW",
                "title": "USC missing", "description": "USC missing",
                "evidence": {}, "suggestion": "",
                "amount_impact": None, "employee_refs": ["E103"],
            },
        ]
        run, exp, cert, bureau = self._make_inputs(findings, 50.0, 30, "violhash")
        pack = build_evidence_pack(run, exp, cert, bureau)

        assert pack["bureau_summary"]["validation_status"] == "FAILED"
        assert pack["bureau_summary"]["confidence"] == "LOW"
        assert pack["validation_summary"]["violations_found"] == 2
        assert pack["exposure_analysis"]["exposure_total"] == 800.0
        assert pack["exposure_analysis"]["employees_impacted"] == 3
        assert len(pack["findings"]) == 3
        ss = pack["validation_summary"]["severity_summary"]
        assert ss["HIGH"] == 2
        assert ss["LOW"] == 1
        assert ss["MEDIUM"] == 0

    def test_round_trip_deterministic(self):
        findings = [_finding("LOW"), _finding("MEDIUM")]
        run, exp, cert, bureau = self._make_inputs(
            findings, 90.0, 20, "detref"
        )
        p1 = build_evidence_pack(run, exp, cert, bureau, dataset_hash="dsh1")
        p2 = build_evidence_pack(run, exp, cert, bureau, dataset_hash="dsh1")
        assert p1 == p2
