"""Tests for core/rules/rule_version_manager.py.

Covers:
- 2025 payroll date loads the 2025 config (ruleset_version "IE-2025.01")
- 2026 payroll date loads the 2026 config (ruleset_version "IE-2026.01")
- Missing year raises ConfigNotFoundError
- RulesetInfo shape and field types
- list_available_years() discovery
- payroll_date input flexibility (date, str, int, datetime)
- Determinism: repeated calls return equal results
- config_dir override via tmp_path
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from core.rules.engine import RULE_ORDER
from core.rules.rule_version_manager import (
    ConfigNotFoundError,
    RulesetInfo,
    list_available_years,
    select_config,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# The bundled config directory (core/rules/) — contains the real JSON files.
_BUNDLED_DIR = Path(__file__).parent.parent / "core" / "rules"


def _write_config(directory: Path, year: int, version: str) -> Path:
    """Write a minimal valid config file for *year* into *directory*."""
    payload = {
        "ruleset_version": version,
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
                "employer_rate_lower": 0.0915,
                "employer_rate_higher": 0.114,
                "weekly_threshold_for_higher": 552,
            }
        },
        "minimum_wage": {"hourly_rate": 12.70},
        "auto_enrolment": {
            "eligibility": {"age_min": 23, "age_max": 60, "annual_earnings_min": 20000}
        },
    }
    path = directory / f"ie_config_{year}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ===========================================================================
# Core behaviour: year routing
# ===========================================================================

class TestYearRouting:

    def test_2025_payroll_loads_2025_rules(self):
        """A payroll date in 2025 must load ie_config_2025.json (IE-2025.01)."""
        info = select_config(date(2025, 6, 15), _BUNDLED_DIR)
        assert info.rule_version == "IE-2025.01"

    def test_2026_payroll_loads_2026_rules(self):
        """A payroll date in 2026 must load ie_config_2026.json (IE-2026.01)."""
        info = select_config(date(2026, 3, 15), _BUNDLED_DIR)
        assert info.rule_version == "IE-2026.01"

    def test_2025_config_is_distinct_from_2026(self):
        """The two bundled configs must have different ruleset_version strings."""
        info_2025 = select_config(date(2025, 1, 1), _BUNDLED_DIR)
        info_2026 = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert info_2025.rule_version != info_2026.rule_version

    def test_2025_config_dict_differs_from_2026(self):
        """The two configs must contain different rate data."""
        cfg_2025 = select_config(date(2025, 1, 1), _BUNDLED_DIR).config
        cfg_2026 = select_config(date(2026, 1, 1), _BUNDLED_DIR).config
        assert cfg_2025 != cfg_2026

    def test_first_day_of_year_routes_correctly(self):
        assert select_config(date(2026, 1, 1), _BUNDLED_DIR).rule_version == "IE-2026.01"

    def test_last_day_of_year_routes_correctly(self):
        assert select_config(date(2025, 12, 31), _BUNDLED_DIR).rule_version == "IE-2025.01"


# ===========================================================================
# Missing version raises ConfigNotFoundError
# ===========================================================================

class TestMissingVersion:

    def test_missing_year_raises_config_not_found_error(self, tmp_path):
        """Requesting a year with no config file must raise ConfigNotFoundError."""
        _write_config(tmp_path, 2026, "IE-2026.01")
        with pytest.raises(ConfigNotFoundError):
            select_config(2099, tmp_path)

    def test_config_not_found_error_is_file_not_found(self, tmp_path):
        """ConfigNotFoundError must derive from FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            select_config(2099, tmp_path)

    def test_config_not_found_error_carries_year(self, tmp_path):
        try:
            select_config(2099, tmp_path)
        except ConfigNotFoundError as exc:
            assert exc.year == 2099
        else:
            pytest.fail("ConfigNotFoundError was not raised")

    def test_config_not_found_error_carries_config_dir(self, tmp_path):
        try:
            select_config(2099, tmp_path)
        except ConfigNotFoundError as exc:
            assert exc.config_dir == tmp_path
        else:
            pytest.fail("ConfigNotFoundError was not raised")

    def test_config_not_found_error_message_mentions_year(self, tmp_path):
        with pytest.raises(ConfigNotFoundError, match="2099"):
            select_config(2099, tmp_path)

    def test_config_not_found_error_message_lists_available_years(self, tmp_path):
        _write_config(tmp_path, 2025, "IE-2025.01")
        _write_config(tmp_path, 2026, "IE-2026.01")
        with pytest.raises(ConfigNotFoundError, match="2025"):
            select_config(2099, tmp_path)

    def test_empty_directory_raises_config_not_found_error(self, tmp_path):
        with pytest.raises(ConfigNotFoundError):
            select_config(2026, tmp_path)


# ===========================================================================
# RulesetInfo shape
# ===========================================================================

class TestRulesetInfoShape:

    def test_returns_ruleset_info_named_tuple(self):
        info = select_config(date(2026, 3, 15), _BUNDLED_DIR)
        assert isinstance(info, RulesetInfo)

    def test_rule_version_is_string(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert isinstance(info.rule_version, str)
        assert info.rule_version  # non-empty

    def test_rules_loaded_is_positive_int(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert isinstance(info.rules_loaded, int)
        assert info.rules_loaded > 0

    def test_rules_loaded_matches_rule_order_length(self):
        """rules_loaded must equal the number of rules in RULE_ORDER."""
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert info.rules_loaded == len(RULE_ORDER)

    def test_config_is_dict(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert isinstance(info.config, dict)

    def test_config_contains_required_sections(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        for section in ("usc", "income_tax", "prsi", "minimum_wage", "auto_enrolment"):
            assert section in info.config, f"Config missing section: {section!r}"

    def test_config_ruleset_version_matches_info_rule_version(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert info.config["ruleset_version"] == info.rule_version

    def test_namedtuple_fields_accessible_by_name(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        # Verify all three fields are accessible by attribute
        _ = info.rule_version
        _ = info.rules_loaded
        _ = info.config

    def test_namedtuple_fields_accessible_by_index(self):
        info = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert info[0] == info.rule_version
        assert info[1] == info.rules_loaded
        assert info[2] == info.config


# ===========================================================================
# payroll_date input flexibility
# ===========================================================================

class TestPayrollDateInputTypes:

    def test_accepts_date_object(self):
        info = select_config(date(2026, 6, 1), _BUNDLED_DIR)
        assert info.rule_version == "IE-2026.01"

    def test_accepts_datetime_object(self):
        info = select_config(datetime(2026, 6, 1, 12, 0, 0), _BUNDLED_DIR)
        assert info.rule_version == "IE-2026.01"

    def test_accepts_iso_date_string(self):
        info = select_config("2026-03-15", _BUNDLED_DIR)
        assert info.rule_version == "IE-2026.01"

    def test_accepts_integer_year(self):
        info = select_config(2026, _BUNDLED_DIR)
        assert info.rule_version == "IE-2026.01"

    def test_accepts_year_string(self):
        info = select_config("2026", _BUNDLED_DIR)
        assert info.rule_version == "IE-2026.01"

    def test_date_and_int_produce_same_result(self):
        by_date = select_config(date(2026, 9, 30), _BUNDLED_DIR)
        by_int = select_config(2026, _BUNDLED_DIR)
        assert by_date.rule_version == by_int.rule_version
        assert by_date.rules_loaded == by_int.rules_loaded

    def test_invalid_string_raises_value_error(self):
        with pytest.raises(ValueError):
            select_config("not-a-date", _BUNDLED_DIR)

    def test_out_of_range_year_raises_value_error(self):
        with pytest.raises(ValueError):
            select_config(99999, _BUNDLED_DIR)


# ===========================================================================
# list_available_years
# ===========================================================================

class TestListAvailableYears:

    def test_bundled_dir_includes_2025_and_2026(self):
        years = list_available_years(_BUNDLED_DIR)
        assert 2025 in years
        assert 2026 in years

    def test_returns_sorted_list(self):
        years = list_available_years(_BUNDLED_DIR)
        assert years == sorted(years)

    def test_returns_list_of_ints(self):
        for y in list_available_years(_BUNDLED_DIR):
            assert isinstance(y, int)

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert list_available_years(tmp_path) == []

    def test_non_config_files_are_ignored(self, tmp_path):
        (tmp_path / "README.txt").write_text("ignored")
        (tmp_path / "ie_config_2026.json").write_text("{}")
        years = list_available_years(tmp_path)
        assert years == [2026]

    def test_custom_dir_with_two_years(self, tmp_path):
        _write_config(tmp_path, 2024, "IE-2024.01")
        _write_config(tmp_path, 2027, "IE-2027.01")
        assert list_available_years(tmp_path) == [2024, 2027]

    def test_default_dir_uses_bundled_location(self):
        """Calling without args must find at least the bundled 2026 config."""
        years = list_available_years()
        assert 2026 in years


# ===========================================================================
# config_dir override
# ===========================================================================

class TestConfigDirOverride:

    def test_custom_dir_loads_correct_config(self, tmp_path):
        _write_config(tmp_path, 2030, "IE-2030.01")
        info = select_config(2030, tmp_path)
        assert info.rule_version == "IE-2030.01"

    def test_custom_dir_does_not_see_bundled_configs(self, tmp_path):
        """A tmp_path with only a 2030 config must not see 2026 from the bundled dir."""
        _write_config(tmp_path, 2030, "IE-2030.01")
        with pytest.raises(ConfigNotFoundError):
            select_config(2026, tmp_path)

    def test_config_dir_as_string_accepted(self, tmp_path):
        _write_config(tmp_path, 2031, "IE-2031.01")
        info = select_config(2031, str(tmp_path))
        assert info.rule_version == "IE-2031.01"

    def test_default_config_dir_used_when_none(self):
        """Passing config_dir=None must fall back to the bundled directory."""
        info = select_config(2026, None)
        assert info.rule_version == "IE-2026.01"


# ===========================================================================
# Determinism
# ===========================================================================

class TestDeterminism:

    def test_repeated_calls_return_equal_rulesetinfo(self):
        r1 = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        r2 = select_config(date(2026, 1, 1), _BUNDLED_DIR)
        assert r1 == r2

    def test_repeated_calls_return_equal_config_dicts(self):
        c1 = select_config(2026, _BUNDLED_DIR).config
        c2 = select_config(2026, _BUNDLED_DIR).config
        assert c1 == c2

    def test_repeated_calls_same_rules_loaded(self):
        assert (
            select_config(2026, _BUNDLED_DIR).rules_loaded
            == select_config(2026, _BUNDLED_DIR).rules_loaded
        )

    def test_list_available_years_is_deterministic(self):
        assert list_available_years(_BUNDLED_DIR) == list_available_years(_BUNDLED_DIR)
