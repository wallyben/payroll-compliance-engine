"""
Phase 6: minimal regulatory security and integrity hardening tests.

Covers:
- sha256_of_bytes(): determinism, known test vectors, format, changed content.
- sha256_of_text(): determinism, known test vector, encoding sensitivity.
- sha256_of_file(): determinism, matches sha256_of_bytes(), large-file chunking,
  changed file content detection.
- verify_hash(): match returns True, mismatch returns False, case-insensitive,
  changed data detected.
- assert_hash_match(): passes on correct hash, raises HashMismatchError on
  mismatch, error message contains context string.
- HashMismatchError: is a ValueError subclass (catch-at-boundary contract).
- Integration: payroll CSV and findings_json payloads are hashed and verified
  deterministically, simulating how the functions fit into the repo.
- Repeated runs of all functions produce identical results.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.security.crypto import (
    HashMismatchError,
    assert_hash_match,
    sha256_of_bytes,
    sha256_of_file,
    sha256_of_text,
    verify_hash,
)

# ---------------------------------------------------------------------------
# Well-known SHA256 test vectors (RFC 4634 / NIST)
# ---------------------------------------------------------------------------
_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
_HELLO_SHA256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
# ---------------------------------------------------------------------------
# sha256_of_bytes()
# ---------------------------------------------------------------------------


def test_sha256_of_bytes_empty_known_vector():
    assert sha256_of_bytes(b"") == _EMPTY_SHA256


def test_sha256_of_bytes_hello_known_vector():
    assert sha256_of_bytes(b"hello") == _HELLO_SHA256


def test_sha256_of_bytes_returns_lowercase_hex():
    result = sha256_of_bytes(b"test")
    assert result == result.lower()
    assert all(c in "0123456789abcdef" for c in result)


def test_sha256_of_bytes_returns_64_chars():
    assert len(sha256_of_bytes(b"any content")) == 64


def test_sha256_of_bytes_deterministic():
    data = b"payroll row 1,1000.00,200.00"
    assert sha256_of_bytes(data) == sha256_of_bytes(data)


def test_sha256_of_bytes_deterministic_across_three_calls():
    data = b"\x00\x01\x02\x03"
    h1 = sha256_of_bytes(data)
    h2 = sha256_of_bytes(data)
    h3 = sha256_of_bytes(data)
    assert h1 == h2 == h3


def test_sha256_of_bytes_different_content_produces_different_hash():
    h1 = sha256_of_bytes(b"original")
    h2 = sha256_of_bytes(b"modified")
    assert h1 != h2


def test_sha256_of_bytes_single_bit_change_produces_different_hash():
    original = b"payroll\x00"
    modified = b"payroll\x01"
    assert sha256_of_bytes(original) != sha256_of_bytes(modified)


def test_sha256_of_bytes_returns_str():
    assert isinstance(sha256_of_bytes(b"data"), str)


# ---------------------------------------------------------------------------
# sha256_of_text()
# ---------------------------------------------------------------------------


def test_sha256_of_text_hello_matches_bytes_vector():
    # sha256_of_text("hello") == sha256_of_bytes(b"hello")
    assert sha256_of_text("hello") == _HELLO_SHA256


def test_sha256_of_text_deterministic():
    text = '{"rule_id": "IE.PAYE.001", "severity": "HIGH"}'
    assert sha256_of_text(text) == sha256_of_text(text)


def test_sha256_of_text_deterministic_across_three_calls():
    text = "same text same hash"
    assert sha256_of_text(text) == sha256_of_text(text) == sha256_of_text(text)


def test_sha256_of_text_different_content_different_hash():
    assert sha256_of_text("version A") != sha256_of_text("version B")


def test_sha256_of_text_encoding_affects_hash():
    text = "hello"
    utf8_hash = sha256_of_text(text, encoding="utf-8")
    utf16_hash = sha256_of_text(text, encoding="utf-16")
    assert utf8_hash != utf16_hash


def test_sha256_of_text_default_encoding_is_utf8():
    text = "Irish payroll \u20ac"  # € sign
    assert sha256_of_text(text) == sha256_of_text(text, encoding="utf-8")


def test_sha256_of_text_matches_sha256_of_bytes():
    text = "findings json payload"
    assert sha256_of_text(text) == sha256_of_bytes(text.encode("utf-8"))


def test_sha256_of_text_returns_64_chars():
    assert len(sha256_of_text("any string")) == 64


def test_sha256_of_text_json_payload_deterministic():
    """Simulates hashing findings_json stored in the Run DB row."""
    payload = json.dumps(
        {"risk_points": 10, "compliance_score": 90, "findings": []},
        sort_keys=True,
    )
    h1 = sha256_of_text(payload)
    h2 = sha256_of_text(payload)
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_of_text_changed_json_different_hash():
    payload_a = json.dumps({"risk_points": 10}, sort_keys=True)
    payload_b = json.dumps({"risk_points": 99}, sort_keys=True)
    assert sha256_of_text(payload_a) != sha256_of_text(payload_b)


# ---------------------------------------------------------------------------
# sha256_of_file()
# ---------------------------------------------------------------------------


def test_sha256_of_file_matches_sha256_of_bytes(tmp_path):
    content = b"employee_id,gross_pay\nE001,1000.00\n"
    f = tmp_path / "payroll.csv"
    f.write_bytes(content)
    assert sha256_of_file(f) == sha256_of_bytes(content)


def test_sha256_of_file_deterministic(tmp_path):
    f = tmp_path / "data.csv"
    f.write_bytes(b"stable content")
    assert sha256_of_file(f) == sha256_of_file(f)


def test_sha256_of_file_deterministic_across_three_calls(tmp_path):
    f = tmp_path / "data.csv"
    f.write_bytes(b"stable content")
    h1 = sha256_of_file(f)
    h2 = sha256_of_file(f)
    h3 = sha256_of_file(f)
    assert h1 == h2 == h3


def test_sha256_of_file_changed_content_different_hash(tmp_path):
    f = tmp_path / "payroll.csv"
    f.write_bytes(b"original,1000.00")
    hash_before = sha256_of_file(f)
    f.write_bytes(b"tampered,9999.00")
    hash_after = sha256_of_file(f)
    assert hash_before != hash_after


def test_sha256_of_file_empty_file_known_vector(tmp_path):
    f = tmp_path / "empty.csv"
    f.write_bytes(b"")
    assert sha256_of_file(f) == _EMPTY_SHA256


def test_sha256_of_file_accepts_str_path(tmp_path):
    f = tmp_path / "data.csv"
    f.write_bytes(b"content")
    result = sha256_of_file(str(f))
    assert isinstance(result, str)
    assert len(result) == 64


def test_sha256_of_file_accepts_path_object(tmp_path):
    f = tmp_path / "data.csv"
    f.write_bytes(b"content")
    result = sha256_of_file(f)
    assert isinstance(result, str)
    assert len(result) == 64


def test_sha256_of_file_large_file_chunked_reading(tmp_path):
    """A file larger than the chunk size must still produce the correct hash."""
    # Write 200 KiB — larger than the 64 KiB chunk size
    content = b"x" * (200 * 1024)
    f = tmp_path / "large.csv"
    f.write_bytes(content)
    assert sha256_of_file(f) == sha256_of_bytes(content)


def test_sha256_of_file_simulates_payroll_upload(tmp_path):
    """Simulate the hash lifecycle of an uploaded payroll CSV."""
    csv_content = (
        b"employee_id,gross_pay,net_pay,paye,usc,prsi_ee\n"
        b"E001,1000.00,788.00,100.00,30.00,42.00\n"
        b"E002,2000.00,1691.00,200.00,25.00,84.00\n"
    )
    upload_path = tmp_path / "payroll_run_001.csv"
    upload_path.write_bytes(csv_content)

    # Hash at upload time
    hash_at_upload = sha256_of_file(upload_path)

    # Hash at run time (file unchanged)
    hash_at_run = sha256_of_file(upload_path)

    # Must be identical — file was not modified
    assert hash_at_upload == hash_at_run

    # Simulate tampering
    tampered = tmp_path / "tampered.csv"
    tampered.write_bytes(csv_content.replace(b"1000.00", b"9999.00"))
    hash_tampered = sha256_of_file(tampered)
    assert hash_tampered != hash_at_upload


# ---------------------------------------------------------------------------
# verify_hash()
# ---------------------------------------------------------------------------


def test_verify_hash_returns_true_for_correct_hash():
    data = b"payroll findings"
    expected = sha256_of_bytes(data)
    assert verify_hash(data, expected) is True


def test_verify_hash_returns_false_for_wrong_hash():
    data = b"payroll findings"
    assert verify_hash(data, _EMPTY_SHA256) is False


def test_verify_hash_is_case_insensitive():
    data = b"hello"
    expected_lower = sha256_of_bytes(data)
    expected_upper = expected_lower.upper()
    assert verify_hash(data, expected_lower) is True
    assert verify_hash(data, expected_upper) is True


def test_verify_hash_changed_data_fails():
    data = b"original content"
    correct_hash = sha256_of_bytes(data)
    assert verify_hash(b"modified content", correct_hash) is False


def test_verify_hash_empty_data():
    assert verify_hash(b"", _EMPTY_SHA256) is True
    assert verify_hash(b"", _HELLO_SHA256) is False


def test_verify_hash_returns_bool():
    result = verify_hash(b"data", sha256_of_bytes(b"data"))
    assert isinstance(result, bool)


def test_verify_hash_is_deterministic():
    data = b"consistent"
    expected = sha256_of_bytes(data)
    assert verify_hash(data, expected) == verify_hash(data, expected)


# ---------------------------------------------------------------------------
# assert_hash_match()
# ---------------------------------------------------------------------------


def test_assert_hash_match_passes_for_matching_hashes():
    h = sha256_of_bytes(b"content")
    assert_hash_match(h, h)  # must not raise


def test_assert_hash_match_raises_for_mismatched_hashes():
    with pytest.raises(HashMismatchError):
        assert_hash_match(_HELLO_SHA256, _EMPTY_SHA256)


def test_assert_hash_match_raises_hash_mismatch_error_type():
    with pytest.raises(HashMismatchError):
        assert_hash_match("aaaa" * 16, "bbbb" * 16)


def test_assert_hash_match_hash_mismatch_error_is_value_error():
    """HashMismatchError must be a ValueError subclass for catch-at-boundary."""
    with pytest.raises(ValueError):
        assert_hash_match("aaaa" * 16, "bbbb" * 16)


def test_assert_hash_match_error_message_contains_context():
    context = "run_42_findings_json"
    with pytest.raises(HashMismatchError, match=context):
        assert_hash_match("aaaa" * 16, "bbbb" * 16, context=context)


def test_assert_hash_match_error_without_context_still_raises():
    with pytest.raises(HashMismatchError):
        assert_hash_match("aaaa" * 16, "bbbb" * 16)


def test_assert_hash_match_is_case_insensitive():
    h = sha256_of_bytes(b"data")
    assert_hash_match(h.upper(), h.lower())  # must not raise
    assert_hash_match(h.lower(), h.upper())  # must not raise


# ---------------------------------------------------------------------------
# HashMismatchError class contract
# ---------------------------------------------------------------------------


def test_hash_mismatch_error_is_value_error_subclass():
    assert issubclass(HashMismatchError, ValueError)


def test_hash_mismatch_error_can_be_caught_as_value_error():
    with pytest.raises(ValueError):
        raise HashMismatchError("tampered")


def test_hash_mismatch_error_message_preserved():
    with pytest.raises(HashMismatchError, match="tampered findings"):
        raise HashMismatchError("tampered findings")


# ---------------------------------------------------------------------------
# Integration: findings_json payload hashing (repo fit demonstration)
# ---------------------------------------------------------------------------


def test_findings_json_hash_is_deterministic():
    """SHA256 of a sort_keys findings_json payload is stable across runs.

    This demonstrates how sha256_of_text can protect the findings_json column
    in the Run DB row: hash at write time, verify at read time.
    """
    payload = json.dumps(
        {
            "score_bundle": {
                "risk_points": 14,
                "compliance_score": 86,
                "risk_band": "LOW_RISK",
                "exposure_total": 150.0,
            },
            "findings": [
                {
                    "rule_id": "IE.PAYE.001",
                    "severity": "HIGH",
                    "title": "Negative PAYE",
                    "description": "desc",
                    "evidence": {"count": 1},
                    "suggestion": "",
                    "amount_impact": None,
                    "employee_refs": ["E001"],
                }
            ],
        },
        sort_keys=True,
    )
    h1 = sha256_of_text(payload)
    h2 = sha256_of_text(payload)
    assert h1 == h2
    assert len(h1) == 64


def test_findings_json_hash_detects_tampering():
    """Modifying a single field in findings_json changes its hash."""
    base = json.dumps({"risk_points": 10, "compliance_score": 90}, sort_keys=True)
    tampered = json.dumps({"risk_points": 0, "compliance_score": 100}, sort_keys=True)
    assert sha256_of_text(base) != sha256_of_text(tampered)


def test_verify_hash_used_for_findings_json_integrity():
    """Simulate the write-then-verify lifecycle for the findings_json column."""
    findings_json = json.dumps({"findings": [], "risk_points": 0}, sort_keys=True)
    stored_hash = sha256_of_text(findings_json)

    # At verification time: recompute and verify
    assert verify_hash(findings_json.encode("utf-8"), stored_hash)

    # Detect tampering
    tampered_json = json.dumps({"findings": [], "risk_points": 999}, sort_keys=True)
    assert not verify_hash(tampered_json.encode("utf-8"), stored_hash)


def test_assert_hash_match_for_findings_json_raises_on_tamper():
    """assert_hash_match raises clearly when findings_json has been tampered."""
    original = json.dumps({"risk_points": 10}, sort_keys=True)
    original_hash = sha256_of_text(original)

    tampered = json.dumps({"risk_points": 0}, sort_keys=True)
    tampered_hash = sha256_of_text(tampered)

    with pytest.raises(HashMismatchError):
        assert_hash_match(tampered_hash, original_hash, context="findings_json run_1")
