"""
tests/test_certificate_generator.py
-------------------------------------
Unit tests for core/reporting/certificate.py.

Test groups:
  1. PASSED status  — no violations
  2. FAILED status  — HIGH / CRITICAL findings
  3. certificate_id — determinism and derivation
  4. Full determinism — identical input → identical certificate
  5. Output contract — field names, types, and values
  6. Pydantic RunOut input — real schema objects accepted
"""

import hashlib

import pytest

from core.reporting.certificate import generate_certificate
from core.rules.engine import RULE_ORDER

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FIXED_DATE = "2026-03-15"
ENGINE_VERSION = "1.0.0"


def _run_out(
    findings=None,
    findings_hash: str = "abc123def456",
    ruleset_version: str = "IE-2026.01",
) -> dict:
    """Minimal RunOut-compatible dict for testing."""
    return {
        "id": 1,
        "upload_id": 10,
        "mapping_id": 5,
        "ruleset_version": ruleset_version,
        "findings": findings or [],
        "counts": {},
        "invalid_rows": [],
        "findings_hash": findings_hash,
    }


def _finding(severity: str, rule_id: str = "IE.PAYE.003") -> dict:
    """Minimal finding dict matching the repo's real structure."""
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": "Test finding",
        "description": "Test description",
        "evidence": {},
        "suggestion": "",
        "amount_impact": None,
        "employee_refs": [],
    }


# ---------------------------------------------------------------------------
# 1. PASSED status
# ---------------------------------------------------------------------------

class TestPassedStatus:
    def test_empty_findings_is_passed(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "PASSED"

    def test_only_low_findings_is_passed(self):
        findings = [_finding("LOW"), _finding("LOW"), _finding("LOW")]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "PASSED"

    def test_only_medium_findings_is_passed(self):
        findings = [_finding("MEDIUM"), _finding("MEDIUM")]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "PASSED"

    def test_mixed_low_and_medium_is_passed(self):
        findings = [_finding("LOW"), _finding("MEDIUM"), _finding("LOW")]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "PASSED"

    def test_violations_found_is_zero_when_passed(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        assert cert["violations_found"] == 0


# ---------------------------------------------------------------------------
# 2. FAILED status
# ---------------------------------------------------------------------------

class TestFailedStatus:
    def test_single_high_finding_fails(self):
        findings = [_finding("HIGH")]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "FAILED"

    def test_multiple_high_findings_fail(self):
        findings = [_finding("HIGH", f"RULE.{i}") for i in range(4)]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "FAILED"

    def test_high_mixed_with_low_and_medium_fails(self):
        findings = [_finding("LOW"), _finding("MEDIUM"), _finding("HIGH")]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "FAILED"

    def test_critical_severity_fails(self):
        """CRITICAL is a failing severity (defensive; reserved for future use)."""
        findings = [_finding("CRITICAL")]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "FAILED"

    def test_violations_found_counts_only_high_and_critical(self):
        findings = [
            _finding("HIGH"),
            _finding("HIGH"),
            _finding("MEDIUM"),
            _finding("LOW"),
            _finding("CRITICAL"),
        ]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["violations_found"] == 3

    def test_violations_found_exact_count(self):
        n = 7
        findings = [_finding("HIGH", f"RULE.{i}") for i in range(n)]
        cert = generate_certificate(_run_out(findings=findings), ENGINE_VERSION, FIXED_DATE)
        assert cert["violations_found"] == n


# ---------------------------------------------------------------------------
# 3. certificate_id determinism and derivation
# ---------------------------------------------------------------------------

class TestCertificateId:
    def test_certificate_id_is_64_char_hex(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        cid = cert["certificate_id"]
        assert len(cid) == 64
        assert all(c in "0123456789abcdef" for c in cid)

    def test_certificate_id_matches_expected_sha256(self):
        findings_hash = "deadbeefcafe1234"
        engine_ver = "2.3.1"
        expected = hashlib.sha256(
            (findings_hash + engine_ver).encode("utf-8")
        ).hexdigest()
        cert = generate_certificate(
            _run_out(findings_hash=findings_hash),
            engine_ver,
            FIXED_DATE,
        )
        assert cert["certificate_id"] == expected

    def test_different_findings_hash_yields_different_id(self):
        cert_a = generate_certificate(_run_out(findings_hash="hash_a"), ENGINE_VERSION, FIXED_DATE)
        cert_b = generate_certificate(_run_out(findings_hash="hash_b"), ENGINE_VERSION, FIXED_DATE)
        assert cert_a["certificate_id"] != cert_b["certificate_id"]

    def test_different_engine_version_yields_different_id(self):
        cert_a = generate_certificate(_run_out(), "1.0.0", FIXED_DATE)
        cert_b = generate_certificate(_run_out(), "2.0.0", FIXED_DATE)
        assert cert_a["certificate_id"] != cert_b["certificate_id"]

    def test_certificate_id_stable_across_ten_calls(self):
        run = _run_out(findings_hash="stablehash999")
        ids = {generate_certificate(run, ENGINE_VERSION, FIXED_DATE)["certificate_id"]
               for _ in range(10)}
        assert len(ids) == 1, "certificate_id must not vary across repeated calls"


# ---------------------------------------------------------------------------
# 4. Full determinism — identical input → identical certificate
# ---------------------------------------------------------------------------

class TestFullDeterminism:
    def test_same_input_produces_identical_certificate(self):
        findings = [_finding("HIGH"), _finding("LOW"), _finding("MEDIUM")]
        run = _run_out(findings=findings, findings_hash="ref42", ruleset_version="IE-2026.01")
        cert1 = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        cert2 = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        assert cert1 == cert2

    def test_input_not_mutated_by_generator(self):
        findings = [_finding("HIGH")]
        run = _run_out(findings=findings, findings_hash="original")
        original_hash = run["findings_hash"]
        generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        assert run["findings_hash"] == original_hash
        assert len(run["findings"]) == 1

    def test_determinism_with_large_findings_list(self):
        findings = [_finding("LOW", f"RULE.{i}") for i in range(50)]
        run = _run_out(findings=findings, findings_hash="largerun")
        cert1 = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        cert2 = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        assert cert1["certificate_id"] == cert2["certificate_id"]
        assert cert1["violations_found"] == cert2["violations_found"]


# ---------------------------------------------------------------------------
# 5. Output contract
# ---------------------------------------------------------------------------

class TestOutputContract:
    def test_all_required_fields_present(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        required = {
            "certificate_id",
            "scan_date",
            "engine_version",
            "rules_version",
            "findings_hash",
            "rules_checked",
            "violations_found",
            "validation_status",
        }
        assert set(cert.keys()) == required

    def test_rules_version_from_run_out(self):
        cert = generate_certificate(
            _run_out(ruleset_version="IE-2026.01"),
            ENGINE_VERSION,
            FIXED_DATE,
        )
        assert cert["rules_version"] == "IE-2026.01"

    def test_engine_version_preserved(self):
        cert = generate_certificate(_run_out(), "3.1.4", FIXED_DATE)
        assert cert["engine_version"] == "3.1.4"

    def test_scan_date_preserved(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, "2025-12-31")
        assert cert["scan_date"] == "2025-12-31"

    def test_findings_hash_passed_through(self):
        cert = generate_certificate(
            _run_out(findings_hash="integrityref"),
            ENGINE_VERSION,
            FIXED_DATE,
        )
        assert cert["findings_hash"] == "integrityref"

    def test_rules_checked_equals_rule_order_length(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        assert cert["rules_checked"] == len(RULE_ORDER)

    def test_rules_checked_is_positive_integer(self):
        cert = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        assert isinstance(cert["rules_checked"], int)
        assert cert["rules_checked"] > 0

    def test_validation_status_only_passed_or_failed(self):
        cert_pass = generate_certificate(_run_out(), ENGINE_VERSION, FIXED_DATE)
        cert_fail = generate_certificate(
            _run_out(findings=[_finding("HIGH")]), ENGINE_VERSION, FIXED_DATE
        )
        assert cert_pass["validation_status"] == "PASSED"
        assert cert_fail["validation_status"] == "FAILED"


# ---------------------------------------------------------------------------
# 6. Pydantic RunOut input
# ---------------------------------------------------------------------------

class TestPydanticRunOutInput:
    def test_pydantic_run_out_accepted(self):
        """generate_certificate must work with a real Pydantic RunOut object."""
        from apps.api.schemas import Finding, RunOut

        findings = [
            Finding(
                rule_id="IE.MINWAGE.001",
                severity="HIGH",
                title="Minimum wage violation",
                description="Hourly rate below statutory minimum",
            )
        ]
        run = RunOut(
            id=1,
            upload_id=1,
            mapping_id=1,
            ruleset_version="IE-2026.01",
            findings=findings,
            counts={"HIGH": 1},
            findings_hash="pydantic_test_hash",
        )
        cert = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "FAILED"
        assert cert["violations_found"] == 1
        assert cert["findings_hash"] == "pydantic_test_hash"
        assert cert["rules_version"] == "IE-2026.01"

    def test_pydantic_run_out_passed_status(self):
        from apps.api.schemas import RunOut

        run = RunOut(
            id=2,
            upload_id=2,
            mapping_id=2,
            ruleset_version="IE-2026.01",
            findings=[],
            counts={},
            findings_hash="clean_run_hash",
        )
        cert = generate_certificate(run, ENGINE_VERSION, FIXED_DATE)
        assert cert["validation_status"] == "PASSED"
        assert cert["violations_found"] == 0
