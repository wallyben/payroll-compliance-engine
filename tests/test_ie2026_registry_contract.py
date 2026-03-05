"""
Golden snapshot test for IE-2026.01 rule registry.
Prevents accidental rule edits. Do not change without explicit registry contract change.
"""
import pytest
from core.rules.registry import (
    REGISTRY,
    RULESET_VERSION,
    all_rule_ids,
    get_meta,
    RuleMeta,
)

# Golden list: exactly 19 rule IDs in deterministic execution order
EXPECTED_IE_2026_RULE_IDS = [
    "IE.NET.001",
    "IE.NET.002",
    "IE.DEDUCT.001",
    "IE.PENSION.002",
    "IE.TOTALS.001",
    "IE.PAY.002",
    "IE.MINWAGE.001",
    "IE.PAY.001",
    "IE.NET.003",
    "IE.DATA.001",
    "IE.PRSI.001",
    "IE.PRSI.004",
    "IE.USC.001",
    "IE.USC.002",
    "IE.AUTOENROL.001",
    "IE.AUTOENROL.002",
    "IE.BIK.001",
    "IE.PRSI.003",
    "IE.DATA.002",
]

VALID_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})
VALID_DOMAINS = frozenset({"arithmetic", "operational", "compliance"})


def test_registry_exactly_19_rules():
    assert len(REGISTRY) == 19


def test_ruleset_version_frozen():
    assert RULESET_VERSION == "IE-2026.01"


def test_rule_ids_match_expected_list():
    ids = all_rule_ids()
    assert ids == EXPECTED_IE_2026_RULE_IDS


def test_each_rule_id_in_registry():
    for rid in EXPECTED_IE_2026_RULE_IDS:
        assert rid in REGISTRY
        assert get_meta(rid) is not None


def test_severities_valid():
    for rid, meta in REGISTRY.items():
        assert meta.severity in VALID_SEVERITIES, f"{rid}: invalid severity {meta.severity}"


def test_domains_valid():
    for rid, meta in REGISTRY.items():
        assert meta.domain in VALID_DOMAINS, f"{rid}: invalid domain {meta.domain}"


def test_exposure_weight_present_and_non_negative():
    for rid, meta in REGISTRY.items():
        assert hasattr(meta, "exposure_weight"), f"{rid}: missing exposure_weight"
        assert isinstance(meta.exposure_weight, int), f"{rid}: exposure_weight must be int"
        assert meta.exposure_weight >= 0, f"{rid}: exposure_weight must be >= 0"


def test_each_meta_has_required_fields():
    for rid, meta in REGISTRY.items():
        assert isinstance(meta, RuleMeta)
        assert meta.rule_id == rid
        assert meta.title
        assert meta.description
        assert meta.remediation
        assert meta.category
        assert meta.ruleset_version == "IE-2026.01"
