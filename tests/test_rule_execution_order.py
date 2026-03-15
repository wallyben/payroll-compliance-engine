"""
Phase 3: rule engine execution-order and determinism tests.

Covers:
- RULE_ORDER constant is in sync with the actual call sequence in run_all().
- All rules named in RULE_ORDER are callable from core.rules.rules.
- RULE_ORDER contains no duplicate entries.
- HIGH-severity deterministic rules precede LOW-severity plausibility rules.
- run_all() produces identical findings on repeated calls with the same input.
- Every finding returned by run_all() contains all REQUIRED_FINDING_KEYS.
- Finding severity values are restricted to HIGH / MEDIUM / LOW.
- finding employee_refs is always a list; evidence is always a dict.
- finding rule_id is always a non-empty string.
- load_ie_config() loads the bundled config and returns expected sections.
- load_ie_config() honours an explicit path override.
- USC bands in the bundled config are in ascending cap order.
- Plausibility rules return empty safely when config is empty or partial.
- Regression: core Irish rule findings remain stable.
- A fully compliant payroll row produces zero findings.
"""

from __future__ import annotations

import json
import re
import inspect
from typing import Any, Dict

import pytest

from core.normalize.schema import CanonicalPayrollRow
from core.rules.engine import (
    REQUIRED_FINDING_KEYS,
    RULE_ORDER,
    load_ie_config,
    run_all,
)
import core.rules.rules as rules_module
from core.rules.rules import (
    rule_prsi_plausibility_class_a,
    rule_usc_plausibility,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BASE_CFG: Dict[str, Any] = {
    "usc": {
        "exemption_limit": 13000,
        "bands": [
            {"cap": 12012, "rate": 0.005},
            {"cap": 28700, "rate": 0.02},
            {"cap": 70044, "rate": 0.03},
            {"cap": None, "rate": 0.08},
        ],
    },
    "income_tax": {
        "standard_rate_band_single": 44000,
        "standard_rate": 0.2,
        "higher_rate": 0.4,
    },
    "prsi": {
        "class_a": {
            "employee_rate_pre_2026_10_01": 0.042,
            "employer_rate_higher": 0.114,
            "employer_rate_lower": 0.0915,
            "weekly_threshold_for_higher": 552,
        }
    },
    "minimum_wage": {"hourly_rate": 12.70},
    "auto_enrolment": {"eligibility": {"annual_earnings_min": 20000}},
}

# A deliberately "dirty" row that will generate findings across several rules,
# useful for checking finding shape without caring which rules fire.
_DIRTY_ROW = CanonicalPayrollRow(
    employee_id="DIRTY", gross_pay=-1.0, net_pay=-500.0
)

# A fully compliant row: all deductions correct, annualised gross above
# auto-enrolment threshold, USC/PRSI within plausibility bands.
# gross=2000, net=1691, paye=200, usc=25, prsi_ee=84, prsi_er=183, pension_ee=0
# Verification:
#   net = 2000 - (200+25+84+0) = 1691  ✓
#   auto_enrolment: 2000*12=24000 >= 20000, pension_ee=0  → no flag  ✓
#   usc plausibility: expected_period ≈ 24.99, 25 within [16.2, 33.7]  ✓
#   prsi plausibility: expected_ee=84, within [50.4, 117.6]  ✓
_CLEAN_ROW = CanonicalPayrollRow(
    employee_id="CLEAN",
    gross_pay=2000.0,
    net_pay=1691.0,
    paye=200.0,
    usc=25.0,
    prsi_ee=84.0,
    prsi_er=183.0,
    pension_ee=0.0,
)

# ---------------------------------------------------------------------------
# RULE_ORDER synchrony with run_all() source
# ---------------------------------------------------------------------------


def test_rule_order_matches_run_all_source():
    """RULE_ORDER must list rules in the exact order run_all() calls them.

    Extracts every ``findings += rule_*(`` call from the run_all source and
    compares the sequence against RULE_ORDER.  Any insertion, deletion, or
    reordering of calls in run_all without a matching update to RULE_ORDER
    will be caught here.
    """
    src = inspect.getsource(run_all)
    pattern = re.compile(r"findings\s*\+=\s*(rule_\w+)\s*\(")
    calls_in_source = pattern.findall(src)
    assert list(calls_in_source) == list(RULE_ORDER), (
        "RULE_ORDER is out of sync with the run_all() body.\n"
        f"Source order : {calls_in_source}\n"
        f"RULE_ORDER   : {list(RULE_ORDER)}"
    )


def test_rule_order_has_no_duplicates():
    assert len(RULE_ORDER) == len(set(RULE_ORDER)), (
        "RULE_ORDER contains duplicate rule names."
    )


def test_rule_order_all_names_callable_from_rules_module():
    """Every name in RULE_ORDER must exist as a callable in core.rules.rules."""
    missing = [
        name for name in RULE_ORDER
        if not callable(getattr(rules_module, name, None))
    ]
    assert missing == [], (
        f"Rule names in RULE_ORDER not found as callables in rules.py: {missing}"
    )


def test_rule_order_is_nonempty():
    assert len(RULE_ORDER) > 0


# ---------------------------------------------------------------------------
# Execution-order invariant: deterministic HIGH rules before LOW plausibility
# ---------------------------------------------------------------------------

_DETERMINISTIC_RULES = [
    "rule_usc_deterministic_bounds",
    "rule_prsi_deterministic_bounds",
    "rule_net_deterministic_upper_bound",
    "rule_paye_deterministic_bounds",
    "rule_minimum_wage_deterministic",
    "rule_auto_enrolment_deterministic",
]
_PLAUSIBILITY_RULES = ["rule_usc_plausibility", "rule_prsi_plausibility_class_a"]


@pytest.mark.parametrize("det_rule", _DETERMINISTIC_RULES)
@pytest.mark.parametrize("plaus_rule", _PLAUSIBILITY_RULES)
def test_deterministic_rule_precedes_plausibility_rule_in_order(det_rule, plaus_rule):
    """Every deterministic HIGH rule must appear before every LOW plausibility
    rule in RULE_ORDER, preventing severity inversion in findings output."""
    order = list(RULE_ORDER)
    assert order.index(det_rule) < order.index(plaus_rule), (
        f"Deterministic rule '{det_rule}' must precede "
        f"plausibility rule '{plaus_rule}' in RULE_ORDER."
    )


# ---------------------------------------------------------------------------
# Required finding keys constant
# ---------------------------------------------------------------------------


def test_required_finding_keys_contains_expected_fields():
    assert REQUIRED_FINDING_KEYS == {
        "rule_id",
        "severity",
        "title",
        "description",
        "evidence",
        "suggestion",
        "amount_impact",
        "employee_refs",
    }


# ---------------------------------------------------------------------------
# Determinism: identical input → identical output, every time
# ---------------------------------------------------------------------------


def test_run_all_empty_rows_is_deterministic():
    assert run_all([], BASE_CFG) == run_all([], BASE_CFG) == []


def test_run_all_clean_row_is_deterministic():
    assert run_all([_CLEAN_ROW], BASE_CFG) == run_all([_CLEAN_ROW], BASE_CFG)


def test_run_all_dirty_row_is_deterministic():
    assert run_all([_DIRTY_ROW], BASE_CFG) == run_all([_DIRTY_ROW], BASE_CFG)


def test_run_all_same_rule_id_sequence_on_repeated_calls():
    """The sequence of rule_ids in findings must be identical across runs."""
    rows = [_CLEAN_ROW, _DIRTY_ROW]
    ids1 = [f["rule_id"] for f in run_all(rows, BASE_CFG)]
    ids2 = [f["rule_id"] for f in run_all(rows, BASE_CFG)]
    assert ids1 == ids2


def test_run_all_multi_row_deterministic():
    rows = [
        CanonicalPayrollRow(employee_id="A", gross_pay=1000.0, net_pay=900.0, prsi_ee=100.0),
        CanonicalPayrollRow(employee_id="B", gross_pay=2000.0, net_pay=1800.0, usc=50.0),
        CanonicalPayrollRow(employee_id="C", gross_pay=500.0, net_pay=450.0, hours=40.0),
    ]
    assert run_all(rows, BASE_CFG) == run_all(rows, BASE_CFG)


# ---------------------------------------------------------------------------
# Finding shape: every finding from run_all must satisfy REQUIRED_FINDING_KEYS
# ---------------------------------------------------------------------------


def test_all_findings_have_required_keys():
    """All required keys must be present in every finding run_all produces."""
    rows = [_DIRTY_ROW,
            CanonicalPayrollRow(employee_id="E2", gross_pay=5000.0, net_pay=5000.0),
            CanonicalPayrollRow(employee_id="E3", gross_pay=100.0, net_pay=90.0, hours=40.0)]
    for f in run_all(rows, BASE_CFG):
        missing = REQUIRED_FINDING_KEYS - set(f.keys())
        assert missing == set(), (
            f"Finding '{f.get('rule_id')}' is missing required keys: {missing}"
        )


def test_all_findings_severity_is_known_value():
    known = {"HIGH", "MEDIUM", "LOW"}
    for f in run_all([_DIRTY_ROW], BASE_CFG):
        assert f["severity"] in known, (
            f"Finding '{f['rule_id']}' has unknown severity '{f['severity']}'"
        )


def test_all_findings_employee_refs_is_list():
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=2000.0)]
    for f in run_all(rows, BASE_CFG):
        assert isinstance(f["employee_refs"], list), (
            f"Finding '{f['rule_id']}' has non-list employee_refs: {type(f['employee_refs'])}"
        )


def test_all_findings_evidence_is_dict():
    for f in run_all([_DIRTY_ROW], BASE_CFG):
        assert isinstance(f["evidence"], dict), (
            f"Finding '{f['rule_id']}' has non-dict evidence: {type(f['evidence'])}"
        )


def test_all_findings_rule_id_is_nonempty_string():
    for f in run_all([_DIRTY_ROW], BASE_CFG):
        assert isinstance(f["rule_id"], str) and f["rule_id"], (
            f"Finding has empty or non-string rule_id: {f.get('rule_id')!r}"
        )


def test_all_findings_rule_id_matches_ie_namespace():
    """All rule_ids produced by the Irish rule engine must start with 'IE.'."""
    for f in run_all([_DIRTY_ROW], BASE_CFG):
        assert f["rule_id"].startswith("IE."), (
            f"Finding has rule_id outside IE namespace: '{f['rule_id']}'"
        )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def test_load_ie_config_returns_dict():
    cfg = load_ie_config()
    assert isinstance(cfg, dict)


def test_load_ie_config_has_required_sections():
    cfg = load_ie_config()
    for section in ("usc", "income_tax", "prsi", "minimum_wage", "auto_enrolment"):
        assert section in cfg, f"Bundled config missing required section: '{section}'"


def test_load_ie_config_ruleset_version():
    assert load_ie_config().get("ruleset_version") == "IE-2026.01"


def test_load_ie_config_usc_bands_ascending():
    """USC bands must be in ascending cap order for the progressive calculator."""
    bands = load_ie_config()["usc"]["bands"]
    caps = [b["cap"] for b in bands if b["cap"] is not None]
    assert caps == sorted(caps), "USC bands are not in ascending cap order."


def test_load_ie_config_minimum_wage_is_positive():
    rate = load_ie_config()["minimum_wage"]["hourly_rate"]
    assert isinstance(rate, (int, float)) and rate > 0


def test_load_ie_config_from_explicit_path(tmp_path):
    """load_ie_config must accept an explicit path override."""
    custom = tmp_path / "custom_config.json"
    payload = {
        "ruleset_version": "TEST-OVERRIDE",
        "usc": {}, "income_tax": {}, "prsi": {},
        "minimum_wage": {}, "auto_enrolment": {},
    }
    custom.write_text(json.dumps(payload))
    cfg = load_ie_config(custom)
    assert cfg["ruleset_version"] == "TEST-OVERRIDE"


def test_load_ie_config_bundled_equals_base_cfg_structure():
    """Bundled config must expose the same top-level keys as the test BASE_CFG."""
    bundled = load_ie_config()
    for key in BASE_CFG:
        assert key in bundled, f"Bundled config missing key present in test BASE_CFG: '{key}'"


# ---------------------------------------------------------------------------
# Config resilience: plausibility rules safe with empty / partial config
# ---------------------------------------------------------------------------


def test_usc_plausibility_safe_with_empty_config():
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, usc=50.0)]
    assert rule_usc_plausibility(rows, {}) == []


def test_prsi_plausibility_safe_with_empty_config():
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, prsi_ee=42.0)]
    assert rule_prsi_plausibility_class_a(rows, {}) == []


def test_usc_plausibility_safe_with_missing_usc_section():
    cfg = {"income_tax": {}, "prsi": {}}
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, usc=50.0)]
    assert rule_usc_plausibility(rows, cfg) == []


def test_prsi_plausibility_safe_with_missing_prsi_section():
    cfg = {"usc": {}, "income_tax": {}}
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, prsi_ee=42.0)]
    assert rule_prsi_plausibility_class_a(rows, cfg) == []


def test_run_all_does_not_raise_with_empty_config():
    """run_all must not raise even when config is empty (no config-dependent
    findings should be produced; structural checks still run)."""
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=800.0)]
    try:
        run_all(rows, {})
    except Exception as exc:
        pytest.fail(f"run_all raised with empty config: {exc}")


# ---------------------------------------------------------------------------
# Regression safety: core Irish rule findings remain stable
# ---------------------------------------------------------------------------


def test_paye_breach_produces_paye_finding():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, paye=-10.0)
    rule_ids = {f["rule_id"] for f in run_all([row], BASE_CFG)}
    assert "IE.PAYE.001" in rule_ids


def test_prsi_bounds_breach_produces_prsi_finding():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, prsi_ee=100.0)
    rule_ids = {f["rule_id"] for f in run_all([row], BASE_CFG)}
    assert "IE.PRSI.002" in rule_ids


def test_usc_bounds_breach_produces_usc_finding():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, usc=1200.0)
    rule_ids = {f["rule_id"] for f in run_all([row], BASE_CFG)}
    assert "IE.USC.002" in rule_ids


def test_min_wage_breach_produces_min_wage_finding():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=100.0, net_pay=90.0, hours=10.0)
    rule_ids = {f["rule_id"] for f in run_all([row], BASE_CFG)}
    assert "IE.MINWAGE.001" in rule_ids


def test_net_upper_bound_breach_produces_net_finding():
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=1000.0, net_pay=800.0,
        paye=200.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    rule_ids = {f["rule_id"] for f in run_all([row], BASE_CFG)}
    assert "IE.NET.002" in rule_ids


def test_clean_payroll_row_produces_no_findings():
    """A payroll row satisfying all Irish compliance rules must produce zero findings."""
    findings = run_all([_CLEAN_ROW], BASE_CFG)
    assert findings == [], (
        f"Unexpected findings for compliant row: {[f['rule_id'] for f in findings]}"
    )


def test_rule_inventory_count_matches_rule_order():
    """RULE_ORDER length must match the number of distinct calls in run_all source."""
    src = inspect.getsource(run_all)
    pattern = re.compile(r"findings\s*\+=\s*(rule_\w+)\s*\(")
    assert len(pattern.findall(src)) == len(RULE_ORDER)
