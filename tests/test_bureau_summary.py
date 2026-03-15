"""
tests/test_bureau_summary.py
-----------------------------
Unit tests for core/reporting/bureau_summary.py.

Test groups:
  1. Clean payroll scan   → PASSED summary, confidence HIGH
  2. Violations present   → FAILED summary, confidence LOW
  3. risk_score           → propagated correctly from run_out.compliance_score
  4. exposure_total       → propagated correctly from exposure_result
  5. Determinism          → identical input → identical output across repeated runs
  6. Confidence levels    → HIGH / MEDIUM / LOW logic
  7. Output contract      → required fields, types
  8. Integration          → round-trip with real exposure_engine + certificate outputs
"""

import pytest

from core.reporting.bureau_summary import generate_bureau_summary

# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------

def _finding(severity: str, rule_id: str = "IE.PAYE.003") -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": "Test",
        "description": "Test",
        "evidence": {},
        "suggestion": "",
        "amount_impact": None,
        "employee_refs": [],
    }


def _run_out(
    findings=None,
    compliance_score: float = 100.0,
    findings_hash: str = "abc123",
) -> dict:
    return {
        "id": 1,
        "upload_id": 1,
        "mapping_id": 1,
        "ruleset_version": "IE-2026.01",
        "findings": findings or [],
        "counts": {},
        "compliance_score": compliance_score,
        "findings_hash": findings_hash,
    }


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
    findings_hash: str = "abc123",
) -> dict:
    return {
        "certificate_id": "deadbeef" * 8,
        "scan_date": "2026-03-15",
        "engine_version": "1.0.0",
        "rules_version": "IE-2026.01",
        "findings_hash": findings_hash,
        "rules_checked": rules_checked,
        "violations_found": violations_found,
        "validation_status": status,
    }


# ---------------------------------------------------------------------------
# 1. Clean payroll scan → PASSED summary
# ---------------------------------------------------------------------------

class TestCleanScan:
    def test_validation_status_is_passed(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(), _certificate(status="PASSED"), 114
        )
        assert summary["validation_status"] == "PASSED"

    def test_violations_found_is_zero(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(), _certificate(), 114
        )
        assert summary["violations_found"] == 0

    def test_exposure_total_is_zero(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(total=0.0), _certificate(), 114
        )
        assert summary["exposure_total"] == 0.0

    def test_confidence_is_high_on_clean_run(self):
        summary = generate_bureau_summary(
            _run_out(findings=[]), _exposure(), _certificate(), 114
        )
        assert summary["confidence"] == "HIGH"

    def test_employees_scanned_propagated(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(), _certificate(), 114
        )
        assert summary["employees_scanned"] == 114


# ---------------------------------------------------------------------------
# 2. Violations present → FAILED summary
# ---------------------------------------------------------------------------

class TestViolationsScan:
    def test_validation_status_is_failed(self):
        findings = [_finding("HIGH"), _finding("HIGH")]
        summary = generate_bureau_summary(
            _run_out(findings=findings),
            _exposure(total=640.0, impacted=2),
            _certificate(status="FAILED", violations_found=2),
            50,
        )
        assert summary["validation_status"] == "FAILED"

    def test_violations_found_count_from_certificate(self):
        findings = [_finding("HIGH"), _finding("HIGH"), _finding("HIGH")]
        summary = generate_bureau_summary(
            _run_out(findings=findings),
            _exposure(total=960.0),
            _certificate(status="FAILED", violations_found=3),
            30,
        )
        assert summary["violations_found"] == 3

    def test_confidence_is_low_on_high_findings(self):
        findings = [_finding("HIGH")]
        summary = generate_bureau_summary(
            _run_out(findings=findings),
            _exposure(),
            _certificate(status="FAILED", violations_found=1),
            10,
        )
        assert summary["confidence"] == "LOW"

    def test_exposure_total_reflected_in_summary(self):
        findings = [_finding("HIGH")]
        summary = generate_bureau_summary(
            _run_out(findings=findings),
            _exposure(total=1920.0),
            _certificate(status="FAILED", violations_found=1),
            20,
        )
        assert summary["exposure_total"] == 1920.0


# ---------------------------------------------------------------------------
# 3. risk_score propagated from compliance_score
# ---------------------------------------------------------------------------

class TestRiskScore:
    def test_full_score_propagated(self):
        summary = generate_bureau_summary(
            _run_out(compliance_score=100.0), _exposure(), _certificate(), 10
        )
        assert summary["risk_score"] == 100

    def test_low_score_propagated(self):
        summary = generate_bureau_summary(
            _run_out(compliance_score=12.0), _exposure(), _certificate(), 10
        )
        assert summary["risk_score"] == 12

    def test_zero_score_propagated(self):
        summary = generate_bureau_summary(
            _run_out(compliance_score=0.0), _exposure(), _certificate(), 10
        )
        assert summary["risk_score"] == 0

    def test_none_score_defaults_to_zero(self):
        run = _run_out()
        run["compliance_score"] = None
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 10)
        assert summary["risk_score"] == 0

    def test_risk_score_is_integer(self):
        summary = generate_bureau_summary(
            _run_out(compliance_score=87.6), _exposure(), _certificate(), 10
        )
        assert isinstance(summary["risk_score"], int)


# ---------------------------------------------------------------------------
# 4. exposure_total propagated from exposure_result
# ---------------------------------------------------------------------------

class TestExposureTotal:
    def test_zero_exposure(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(total=0.0), _certificate(), 10
        )
        assert summary["exposure_total"] == 0.0

    def test_nonzero_exposure(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(total=3840.50), _certificate(), 10
        )
        assert summary["exposure_total"] == 3840.50

    def test_fractional_exposure_preserved(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(total=99.99), _certificate(), 10
        )
        assert summary["exposure_total"] == 99.99


# ---------------------------------------------------------------------------
# 5. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_inputs_produce_identical_output(self):
        findings = [_finding("HIGH"), _finding("LOW")]
        run = _run_out(findings=findings, compliance_score=40.0, findings_hash="ref99")
        exp = _exposure(total=500.0, impacted=2)
        cert = _certificate(status="FAILED", violations_found=1, findings_hash="ref99")

        s1 = generate_bureau_summary(run, exp, cert, 50)
        s2 = generate_bureau_summary(run, exp, cert, 50)
        assert s1 == s2

    def test_stable_across_ten_calls(self):
        run = _run_out(compliance_score=75.0, findings_hash="stableref")
        exp = _exposure(total=0.0)
        cert = _certificate()
        summaries = [generate_bureau_summary(run, exp, cert, 30) for _ in range(10)]
        assert all(s == summaries[0] for s in summaries)

    def test_inputs_not_mutated(self):
        run = _run_out(findings=[_finding("HIGH")])
        exp = _exposure(total=100.0)
        cert = _certificate(status="FAILED", violations_found=1)
        original_hash = run["findings_hash"]
        original_findings_len = len(run["findings"])
        generate_bureau_summary(run, exp, cert, 10)
        assert run["findings_hash"] == original_hash
        assert len(run["findings"]) == original_findings_len


# ---------------------------------------------------------------------------
# 6. Confidence levels
# ---------------------------------------------------------------------------

class TestConfidenceLevels:
    def test_no_findings_gives_high_confidence(self):
        run = _run_out(findings=[])
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "HIGH"

    def test_only_low_findings_gives_medium_confidence(self):
        findings = [_finding("LOW"), _finding("LOW")]
        run = _run_out(findings=findings)
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "MEDIUM"

    def test_only_medium_findings_gives_medium_confidence(self):
        findings = [_finding("MEDIUM"), _finding("MEDIUM")]
        run = _run_out(findings=findings)
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "MEDIUM"

    def test_mixed_low_and_medium_gives_medium_confidence(self):
        findings = [_finding("LOW"), _finding("MEDIUM"), _finding("LOW")]
        run = _run_out(findings=findings)
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "MEDIUM"

    def test_single_high_finding_gives_low_confidence(self):
        findings = [_finding("LOW"), _finding("HIGH")]
        run = _run_out(findings=findings)
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "LOW"

    def test_all_high_findings_gives_low_confidence(self):
        findings = [_finding("HIGH"), _finding("HIGH")]
        run = _run_out(findings=findings)
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "LOW"

    def test_critical_finding_gives_low_confidence(self):
        """CRITICAL is treated as failing severity (defensive)."""
        findings = [_finding("CRITICAL")]
        run = _run_out(findings=findings)
        summary = generate_bureau_summary(run, _exposure(), _certificate(), 5)
        assert summary["confidence"] == "LOW"


# ---------------------------------------------------------------------------
# 7. Output contract
# ---------------------------------------------------------------------------

class TestOutputContract:
    def test_all_required_fields_present(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(), _certificate(), 10
        )
        required = {
            "validation_status",
            "risk_score",
            "exposure_total",
            "employees_scanned",
            "rules_checked",
            "violations_found",
            "findings_hash",
            "confidence",
        }
        assert set(summary.keys()) == required

    def test_rules_checked_from_certificate(self):
        summary = generate_bureau_summary(
            _run_out(), _exposure(), _certificate(rules_checked=29), 10
        )
        assert summary["rules_checked"] == 29

    def test_findings_hash_from_certificate(self):
        summary = generate_bureau_summary(
            _run_out(findings_hash="runhash"),
            _exposure(),
            _certificate(findings_hash="certhash"),
            10,
        )
        assert summary["findings_hash"] == "certhash"

    def test_findings_hash_falls_back_to_run_out(self):
        """If certificate has empty hash, fall back to run_out's hash."""
        cert = _certificate()
        cert["findings_hash"] = ""
        summary = generate_bureau_summary(
            _run_out(findings_hash="runhash"),
            _exposure(),
            cert,
            10,
        )
        assert summary["findings_hash"] == "runhash"

    def test_validation_status_values(self):
        passed = generate_bureau_summary(_run_out(), _exposure(), _certificate(status="PASSED"), 10)
        failed = generate_bureau_summary(
            _run_out(findings=[_finding("HIGH")]),
            _exposure(),
            _certificate(status="FAILED", violations_found=1),
            10,
        )
        assert passed["validation_status"] == "PASSED"
        assert failed["validation_status"] == "FAILED"

    def test_employees_scanned_is_int(self):
        summary = generate_bureau_summary(_run_out(), _exposure(), _certificate(), 77)
        assert isinstance(summary["employees_scanned"], int)
        assert summary["employees_scanned"] == 77


# ---------------------------------------------------------------------------
# 8. Integration — round-trip with real sub-module outputs
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_round_trip_clean_run(self):
        """Full pipeline integration: clean findings → PASSED, confidence HIGH."""
        from core.reporting.exposure_engine import quantify_exposure
        from core.reporting.certificate import generate_certificate

        run = _run_out(findings=[], compliance_score=100.0, findings_hash="cleanhash")
        exp = quantify_exposure(run["findings"])
        cert = generate_certificate(run, engine_version="1.0.0", scan_date="2026-03-15")

        summary = generate_bureau_summary(run, exp, cert, 50)

        assert summary["validation_status"] == "PASSED"
        assert summary["confidence"] == "HIGH"
        assert summary["exposure_total"] == 0.0
        assert summary["violations_found"] == 0
        assert summary["employees_scanned"] == 50
        assert summary["risk_score"] == 100

    def test_round_trip_violations(self):
        """Full pipeline integration: HIGH findings → FAILED, confidence LOW."""
        from core.reporting.exposure_engine import quantify_exposure
        from core.reporting.certificate import generate_certificate

        findings = [
            {
                "rule_id": "IE.MINWAGE.001",
                "severity": "HIGH",
                "title": "Minimum wage violation",
                "description": "Hourly rate below statutory minimum",
                "evidence": {},
                "suggestion": "",
                "amount_impact": 320.0,
                "employee_refs": ["E101"],
            },
            {
                "rule_id": "IE.MINWAGE.001",
                "severity": "HIGH",
                "title": "Minimum wage violation",
                "description": "Hourly rate below statutory minimum",
                "evidence": {},
                "suggestion": "",
                "amount_impact": 480.0,
                "employee_refs": ["E102"],
            },
        ]
        run = _run_out(findings=findings, compliance_score=60.0, findings_hash="violhash")
        exp = quantify_exposure(findings)
        cert = generate_certificate(run, engine_version="1.0.0", scan_date="2026-03-15")

        summary = generate_bureau_summary(run, exp, cert, 30)

        assert summary["validation_status"] == "FAILED"
        assert summary["confidence"] == "LOW"
        assert summary["exposure_total"] == 800.0
        assert summary["violations_found"] == 2
        assert summary["risk_score"] == 60

    def test_round_trip_deterministic(self):
        """Identical inputs to the full pipeline produce identical summaries."""
        from core.reporting.exposure_engine import quantify_exposure
        from core.reporting.certificate import generate_certificate

        run = _run_out(
            findings=[_finding("LOW"), _finding("MEDIUM")],
            compliance_score=85.0,
            findings_hash="detref",
        )
        exp = quantify_exposure(run["findings"])
        cert = generate_certificate(run, "1.0.0", "2026-03-15")

        s1 = generate_bureau_summary(run, exp, cert, 20)
        s2 = generate_bureau_summary(run, exp, cert, 20)
        assert s1 == s2
