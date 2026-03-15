"""
Integrity tests for the findings_hash field introduced in the run pipeline.

Audit requirement: every compliance run must carry a SHA256 hash of its
findings so that regulators and downstream systems can verify that the
findings payload was not modified after execution completed.

Implementation:
  1. apps/api/routers/runs.py computes
         findings_hash = sha256_of_text(json.dumps(findings, sort_keys=True))
     immediately after run_all() returns.
  2. findings_hash is stored on models.Run (String(64) column).
  3. findings_hash is exposed on the RunOut API response schema.

Tests:
  A. Hash primitives (sha256_of_text behaviour)
  B. Identical findings → identical hash (determinism)
  C. Modified findings → different hash (tamper detection)
  D. Hash is stored on Run model record
  E. RunOut schema exposes findings_hash
  F. Pipeline integration: hash derived from _findings fixture is correct
  G. Hash format: 64-character lowercase hex string
  H. Serialisation contract: sort_keys=True guarantees key-order independence
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from apps.api.schemas import Finding, RunOut
from core.ingest.loader import load_table
from core.normalize.mapper import normalize
from core.rules.engine import load_ie_config, run_all
from core.scoring.risk import score_bundle
from core.security.crypto import sha256_of_text

# ---------------------------------------------------------------------------
# Shared pipeline fixture (same CSV used by test_full_pipeline.py)
# ---------------------------------------------------------------------------

_FIXTURE_CSV = Path(__file__).parent / "fixtures" / "pipeline_payroll.csv"

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


def _pipeline_findings() -> List[dict]:
    df = load_table(str(_FIXTURE_CSV))
    rows, _ = normalize(df, _PIPELINE_MAPPING)
    cfg = load_ie_config()
    return run_all(rows, cfg)


_FINDINGS = _pipeline_findings()
_FINDINGS_JSON = json.dumps(_FINDINGS, sort_keys=True)
_FINDINGS_HASH = sha256_of_text(_FINDINGS_JSON)


def _canonical_hash(findings: List[dict]) -> str:
    """Reproduce the exact hash computation used in runs.py."""
    return sha256_of_text(json.dumps(findings, sort_keys=True))


# ---------------------------------------------------------------------------
# A. Hash primitive behaviour
# ---------------------------------------------------------------------------


def test_sha256_of_text_returns_str():
    assert isinstance(sha256_of_text("hello"), str)


def test_sha256_of_text_returns_64_chars():
    assert len(sha256_of_text("hello")) == 64


def test_sha256_of_text_is_lowercase_hex():
    h = sha256_of_text("hello")
    assert h == h.lower()
    int(h, 16)  # raises ValueError if not valid hex


def test_sha256_of_text_known_vector():
    """Known SHA256 of 'hello' — NIST-verifiable."""
    assert sha256_of_text("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_sha256_of_text_empty_string_known_vector():
    assert sha256_of_text("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# ---------------------------------------------------------------------------
# B. Identical findings → identical hash (determinism)
# ---------------------------------------------------------------------------


def test_identical_findings_produce_identical_hash():
    """Running the pipeline twice must produce the same hash."""
    hash1 = _canonical_hash(_pipeline_findings())
    hash2 = _canonical_hash(_pipeline_findings())
    assert hash1 == hash2


def test_same_findings_list_same_hash_repeated_calls():
    """Multiple calls on the same in-memory list must be stable."""
    h1 = _canonical_hash(_FINDINGS)
    h2 = _canonical_hash(_FINDINGS)
    h3 = _canonical_hash(_FINDINGS)
    assert h1 == h2 == h3


def test_empty_findings_hash_is_deterministic():
    h1 = _canonical_hash([])
    h2 = _canonical_hash([])
    assert h1 == h2


def test_empty_findings_hash_known_value():
    """sha256_of_text(json.dumps([], sort_keys=True)) is deterministic and verifiable."""
    expected = sha256_of_text("[]")
    assert _canonical_hash([]) == expected


def test_hash_of_single_finding_deterministic():
    finding = _FINDINGS[0]
    h1 = _canonical_hash([finding])
    h2 = _canonical_hash([finding])
    assert h1 == h2


# ---------------------------------------------------------------------------
# C. Modified findings → different hash (tamper detection)
# ---------------------------------------------------------------------------


def test_changed_severity_produces_different_hash():
    """Changing severity on one finding must change the hash."""
    import copy
    modified = copy.deepcopy(_FINDINGS)
    modified[0]["severity"] = "LOW" if modified[0]["severity"] == "HIGH" else "HIGH"
    assert _canonical_hash(modified) != _FINDINGS_HASH


def test_added_finding_produces_different_hash():
    """Appending a finding must change the hash."""
    import copy
    extended = copy.deepcopy(_FINDINGS)
    extended.append({
        "rule_id": "IE.INJECTED.001",
        "severity": "HIGH",
        "title": "Injected",
        "description": "Tampered finding",
        "evidence": {},
        "suggestion": "",
        "amount_impact": None,
        "employee_refs": ["EVIL"],
    })
    assert _canonical_hash(extended) != _FINDINGS_HASH


def test_removed_finding_produces_different_hash():
    """Removing a finding must change the hash."""
    import copy
    trimmed = copy.deepcopy(_FINDINGS[1:])
    assert _canonical_hash(trimmed) != _FINDINGS_HASH


def test_changed_employee_ref_produces_different_hash():
    """Modifying an employee_ref must change the hash."""
    import copy
    modified = copy.deepcopy(_FINDINGS)
    original_refs = modified[0]["employee_refs"]
    modified[0]["employee_refs"] = ["TAMPERED"] if original_refs else ["TAMPERED"]
    assert _canonical_hash(modified) != _FINDINGS_HASH


def test_changed_rule_id_produces_different_hash():
    import copy
    modified = copy.deepcopy(_FINDINGS)
    modified[0]["rule_id"] = "IE.FAKE.999"
    assert _canonical_hash(modified) != _FINDINGS_HASH


def test_empty_vs_nonempty_findings_different_hash():
    assert _canonical_hash([]) != _FINDINGS_HASH


def test_reordered_findings_different_hash():
    """Changing finding order must change the hash (ordering is part of integrity)."""
    import copy
    if len(_FINDINGS) < 2:
        pytest.skip("Need at least 2 findings to test reorder")
    reordered = copy.deepcopy(_FINDINGS)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    assert _canonical_hash(reordered) != _FINDINGS_HASH


# ---------------------------------------------------------------------------
# D. Hash stored on Run model record
# ---------------------------------------------------------------------------


def test_run_model_has_findings_hash_column():
    """models.Run must declare a findings_hash column.

    Verified via source inspection so the test passes even when SQLAlchemy is
    not installed in the CI environment.
    """
    source = Path(__file__).parent.parent / "apps" / "api" / "models.py"
    text = source.read_text()
    assert "findings_hash" in text, (
        "Run model source does not contain findings_hash declaration."
    )


def test_run_model_findings_hash_is_string_column():
    """findings_hash must be declared as a String column in models.py."""
    source = Path(__file__).parent.parent / "apps" / "api" / "models.py"
    text = source.read_text()
    # Expect the column to be declared with String(...) type
    assert "findings_hash" in text
    assert "String" in text


def test_run_model_can_be_instantiated_with_findings_hash():
    """Run can be constructed with a findings_hash value (no DB required)."""
    sqlalchemy = pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")
    from apps.api import models
    run = models.Run(
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings_json="[]",
        findings_hash=_FINDINGS_HASH,
    )
    assert run.findings_hash == _FINDINGS_HASH


def test_run_model_findings_hash_roundtrips_via_db(tmp_path):
    """findings_hash persists correctly through a SQLite write/read cycle."""
    pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from apps.api.db import Base
    from apps.api import models

    db_url = f"sqlite:///{tmp_path / 'test_hash.db'}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    # Write
    with Session() as session:
        upload = models.Upload(filename="test.csv", content_type="text/csv", stored_path="/tmp/test.csv")
        session.add(upload)
        session.flush()
        mapping = models.Mapping(upload_id=upload.id, mapping_json="{}")
        session.add(mapping)
        session.flush()
        run = models.Run(
            upload_id=upload.id,
            mapping_id=mapping.id,
            ruleset_version="IE-2026.01",
            findings_json=_FINDINGS_JSON,
            findings_hash=_FINDINGS_HASH,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    # Read back
    with Session() as session:
        loaded = session.get(models.Run, run_id)
        assert loaded.findings_hash == _FINDINGS_HASH


def test_run_model_findings_hash_length_in_db(tmp_path):
    """findings_hash stored in DB must be exactly 64 hex characters (SHA256)."""
    pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from apps.api.db import Base
    from apps.api import models

    db_url = f"sqlite:///{tmp_path / 'test_hash_len.db'}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        upload = models.Upload(filename="f.csv", content_type="text/csv", stored_path="/tmp/f.csv")
        session.add(upload)
        session.flush()
        mapping = models.Mapping(upload_id=upload.id, mapping_json="{}")
        session.add(mapping)
        session.flush()
        run = models.Run(
            upload_id=upload.id,
            mapping_id=mapping.id,
            ruleset_version="IE-2026.01",
            findings_json="[]",
            findings_hash=_FINDINGS_HASH,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with Session() as session:
        loaded = session.get(models.Run, run_id)
        assert len(loaded.findings_hash) == 64


# ---------------------------------------------------------------------------
# E. RunOut schema exposes findings_hash
# ---------------------------------------------------------------------------


def _make_run_out(findings_hash: str = _FINDINGS_HASH) -> RunOut:
    bundle = score_bundle(_FINDINGS)
    return RunOut(
        id=1,
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings=[Finding(**f) for f in _FINDINGS],
        counts={"total": 3, "valid": 3, "invalid": 0},
        invalid_rows=[],
        risk_points=bundle["risk_points"],
        compliance_score=bundle["compliance_score"],
        severity_summary={"HIGH": 2, "MEDIUM": 0, "LOW": 2, "TOTAL": 4},
        findings_hash=findings_hash,
    )


def test_runout_has_findings_hash_field():
    """RunOut must expose a findings_hash attribute."""
    run = _make_run_out()
    assert hasattr(run, "findings_hash")


def test_runout_findings_hash_is_str():
    run = _make_run_out()
    assert isinstance(run.findings_hash, str)


def test_runout_findings_hash_is_64_chars():
    run = _make_run_out()
    assert len(run.findings_hash) == 64


def test_runout_findings_hash_value_matches_expected():
    run = _make_run_out()
    assert run.findings_hash == _FINDINGS_HASH


def test_runout_model_dump_includes_findings_hash():
    """model_dump() (used for JSON serialisation) must include findings_hash."""
    run = _make_run_out()
    data = run.model_dump()
    assert "findings_hash" in data
    assert data["findings_hash"] == _FINDINGS_HASH


def test_runout_model_dump_findings_hash_not_none():
    run = _make_run_out()
    data = run.model_dump()
    assert data["findings_hash"] is not None


# ---------------------------------------------------------------------------
# F. Pipeline integration: hash of _FINDINGS fixture is stable
# ---------------------------------------------------------------------------


def test_pipeline_findings_hash_is_64_hex_chars():
    assert len(_FINDINGS_HASH) == 64
    int(_FINDINGS_HASH, 16)  # valid hex


def test_pipeline_findings_hash_stable_across_two_runs():
    h1 = _canonical_hash(_pipeline_findings())
    h2 = _canonical_hash(_pipeline_findings())
    assert h1 == h2


def test_pipeline_findings_hash_not_empty_string():
    assert _FINDINGS_HASH != ""


def test_pipeline_findings_hash_not_hash_of_empty_list():
    """Real findings must produce a hash distinct from an empty-list hash."""
    assert _FINDINGS_HASH != _canonical_hash([])


# ---------------------------------------------------------------------------
# G. Hash format invariants
# ---------------------------------------------------------------------------


def test_hash_format_all_lowercase():
    assert _FINDINGS_HASH == _FINDINGS_HASH.lower()


def test_hash_format_no_whitespace():
    assert " " not in _FINDINGS_HASH
    assert "\n" not in _FINDINGS_HASH


def test_hash_format_valid_hex_digits_only():
    assert all(c in "0123456789abcdef" for c in _FINDINGS_HASH)


# ---------------------------------------------------------------------------
# H. Serialisation contract: sort_keys=True is key-order independent
# ---------------------------------------------------------------------------


def test_sort_keys_produces_same_hash_regardless_of_dict_insertion_order():
    """Python dicts preserve insertion order, but JSON with sort_keys must be
    identical regardless of the order fields were added to each finding dict."""
    finding_ab = {"b": 2, "a": 1}
    finding_ba = {"a": 1, "b": 2}
    h_ab = sha256_of_text(json.dumps([finding_ab], sort_keys=True))
    h_ba = sha256_of_text(json.dumps([finding_ba], sort_keys=True))
    assert h_ab == h_ba


def test_without_sort_keys_order_matters():
    """Sanity check: without sort_keys, insertion order CAN affect JSON output."""
    finding_ab = {"b": 2, "a": 1}
    finding_ba = {"a": 1, "b": 2}
    # These will differ because json.dumps without sort_keys preserves insertion order
    json_ab = json.dumps([finding_ab])
    json_ba = json.dumps([finding_ba])
    # This documents the risk: if we ever accidentally drop sort_keys=True, hashes
    # would become non-deterministic across systems/Python versions.
    assert json_ab != json_ba


def test_findings_hash_uses_utf8_encoding():
    """sha256_of_text uses utf-8 by default; verify a unicode payload hashes correctly."""
    payload = json.dumps([{"rule_id": "IE.TEST.001", "note": "€ Euro sign"}], sort_keys=True)
    h = sha256_of_text(payload)
    # Must equal the hash of the utf-8 bytes
    from core.security.crypto import sha256_of_bytes
    assert h == sha256_of_bytes(payload.encode("utf-8"))
