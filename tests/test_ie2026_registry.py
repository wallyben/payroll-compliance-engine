"""Tests for IE-2026.01 rule metadata registry."""
import pytest
from core.rules.registry import (
    REGISTRY,
    RULESET_VERSION,
    get_meta,
    all_rule_ids,
    RuleMeta,
)


def test_registry_has_19_rules():
    assert len(REGISTRY) == 19


def test_ruleset_version():
    assert RULESET_VERSION == "IE-2026.01"


def test_all_rule_ids_deterministic_order():
    ids = all_rule_ids()
    assert len(ids) == 19
    assert ids[0] == "IE.NET.001"
    assert "IE.TOTALS.001" in ids
    assert "IE.DATA.001" in ids
    assert "IE.DATA.002" in ids


def test_get_meta_returns_rule_meta():
    meta = get_meta("IE.NET.001")
    assert meta is not None
    assert isinstance(meta, RuleMeta)
    assert meta.rule_id == "IE.NET.001"
    assert meta.severity == "CRITICAL"
    assert meta.domain == "arithmetic"
    assert meta.ruleset_version == "IE-2026.01"
    assert meta.exposure_weight == 100


def test_get_meta_unknown_returns_none():
    assert get_meta("IE.UNKNOWN.999") is None


def test_severity_allowed_values():
    for rid, meta in REGISTRY.items():
        assert meta.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"), f"{rid} has bad severity"


def test_each_rule_has_required_metadata():
    for rid, meta in REGISTRY.items():
        assert meta.title
        assert meta.description
        assert meta.remediation
        assert meta.exposure_weight >= 0
        assert meta.domain in ("arithmetic", "operational", "compliance")
        assert meta.category
