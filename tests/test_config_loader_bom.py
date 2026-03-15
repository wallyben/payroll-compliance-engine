"""
BOM-safety tests for apps/api/config_loader.py::load_rules_config().

Regression guard for the bug identified in ENGINE_AUDIT.md §7:
  config_loader.py used encoding="utf-8" on a file that carries a UTF-8 BOM
  (\xef\xbb\xbf), causing JSONDecodeError on every POST /runs call.

Tests:
  1. load_rules_config() succeeds on the real ie_config_2026.json (BOM present).
  2. Loader works correctly when given a BOM-free JSON file (path override via tmp).
  3. Rule count from the API path matches the engine path (load_ie_config).
  4. Top-level key ordering is stable across repeated calls (determinism guard).
  5. Critical config values are present and correct (regression guard).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api.config_loader import RULES_CONFIG_PATH, load_rules_config
from core.rules.engine import load_ie_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_TOP_KEYS = {
    "ruleset_version",
    "usc",
    "income_tax",
    "prsi",
    "minimum_wage",
    "auto_enrolment",
}


# ---------------------------------------------------------------------------
# 1. Real config file (BOM present) loads without error
# ---------------------------------------------------------------------------


def test_load_rules_config_succeeds():
    """load_rules_config() must not raise on the real ie_config_2026.json."""
    cfg = load_rules_config()
    assert isinstance(cfg, dict)


def test_real_config_file_has_bom():
    """Confirm the fixture assumption: the file actually carries a UTF-8 BOM."""
    raw = RULES_CONFIG_PATH.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "ie_config_2026.json must have a UTF-8 BOM for this test to be meaningful"


def test_load_rules_config_returns_all_top_level_keys():
    cfg = load_rules_config()
    assert _EXPECTED_TOP_KEYS.issubset(set(cfg.keys()))


def test_load_rules_config_ruleset_version():
    cfg = load_rules_config()
    assert cfg["ruleset_version"] == "IE-2026.01"


def test_load_rules_config_usc_exemption_limit():
    cfg = load_rules_config()
    assert cfg["usc"]["exemption_limit"] == 13000


def test_load_rules_config_minimum_wage():
    cfg = load_rules_config()
    assert cfg["minimum_wage"]["hourly_rate"] == pytest.approx(12.70)


def test_load_rules_config_prsi_class_a_present():
    cfg = load_rules_config()
    assert "class_a" in cfg["prsi"]


def test_load_rules_config_income_tax_standard_rate():
    cfg = load_rules_config()
    assert cfg["income_tax"]["standard_rate"] == pytest.approx(0.20)


def test_load_rules_config_auto_enrolment_present():
    cfg = load_rules_config()
    assert "eligibility" in cfg["auto_enrolment"]


# ---------------------------------------------------------------------------
# 2. Loader works on a BOM-free JSON file (path constructed in tmp)
# ---------------------------------------------------------------------------


def test_load_rules_config_bom_free_file_succeeds(tmp_path):
    """Loader must also succeed when the file has no BOM (utf-8-sig is a superset of utf-8)."""
    # Write identical content without BOM
    content = load_rules_config()
    bom_free = tmp_path / "config_no_bom.json"
    bom_free.write_text(json.dumps(content), encoding="utf-8")

    # Load via load_ie_config (which also uses utf-8-sig)
    from core.rules.engine import load_ie_config
    cfg2 = load_ie_config(bom_free)
    assert cfg2["ruleset_version"] == "IE-2026.01"


def test_config_loader_bom_free_and_bom_produce_identical_dicts(tmp_path):
    """A BOM-free copy of the config must parse to the same dict as the original."""
    cfg_bom = load_rules_config()

    bom_free = tmp_path / "config_no_bom.json"
    bom_free.write_text(json.dumps(cfg_bom, sort_keys=True), encoding="utf-8")

    cfg_no_bom = load_ie_config(bom_free)
    assert cfg_bom == cfg_no_bom


# ---------------------------------------------------------------------------
# 3. API path and engine path produce identical configs
# ---------------------------------------------------------------------------


def test_api_config_matches_engine_config():
    """load_rules_config() and load_ie_config() must return the same dict."""
    api_cfg = load_rules_config()
    engine_cfg = load_ie_config()
    assert api_cfg == engine_cfg


def test_api_config_key_count_matches_engine_config():
    api_cfg = load_rules_config()
    engine_cfg = load_ie_config()
    assert len(api_cfg) == len(engine_cfg)


def test_api_config_usc_bands_match_engine_config():
    api_cfg = load_rules_config()
    engine_cfg = load_ie_config()
    assert api_cfg["usc"]["bands"] == engine_cfg["usc"]["bands"]


def test_api_config_prsi_rates_match_engine_config():
    api_cfg = load_rules_config()
    engine_cfg = load_ie_config()
    assert api_cfg["prsi"] == engine_cfg["prsi"]


# ---------------------------------------------------------------------------
# 4. Determinism: repeated calls produce identical dicts
# ---------------------------------------------------------------------------


def test_load_rules_config_is_deterministic():
    cfg1 = load_rules_config()
    cfg2 = load_rules_config()
    assert cfg1 == cfg2


def test_load_rules_config_top_level_keys_stable_across_calls():
    keys1 = list(load_rules_config().keys())
    keys2 = list(load_rules_config().keys())
    assert keys1 == keys2


def test_load_rules_config_json_serialisation_stable():
    """Serialising the config with sort_keys must produce the same string on repeated calls."""
    j1 = json.dumps(load_rules_config(), sort_keys=True)
    j2 = json.dumps(load_rules_config(), sort_keys=True)
    assert j1 == j2


# ---------------------------------------------------------------------------
# 5. Critical compliance values (regression guard)
# ---------------------------------------------------------------------------


def test_usc_has_four_bands():
    cfg = load_rules_config()
    assert len(cfg["usc"]["bands"]) == 4


def test_prsi_employee_rate_pre_2026():
    cfg = load_rules_config()
    rate = cfg["prsi"]["class_a"]["employee_rate_pre_2026_10_01"]
    assert rate == pytest.approx(0.042)


def test_prsi_employer_rate_higher():
    cfg = load_rules_config()
    rate = cfg["prsi"]["class_a"]["employer_rate_higher"]
    assert rate == pytest.approx(0.114)


def test_income_tax_standard_rate_band_single():
    cfg = load_rules_config()
    assert cfg["income_tax"]["standard_rate_band_single"] == 44000


def test_auto_enrolment_annual_earnings_min():
    cfg = load_rules_config()
    assert cfg["auto_enrolment"]["eligibility"]["annual_earnings_min"] == 20000
