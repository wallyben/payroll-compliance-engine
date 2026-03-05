"""
Config contract test: ie_config_2026.json must contain required keys for IE-2026.01 rules.
"""
import json
from pathlib import Path

import pytest

from core.rules.config_contract import validate_config_contract

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "rules" / "ie_config_2026.json"


def test_config_has_required_keys():
    """Loaded config passes contract validation."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    validate_config_contract(config)


def test_config_missing_key_raises():
    """Missing required key raises ValueError with clear message."""
    config = {"minimum_wage": {"hourly_rate": 12.70}}
    with pytest.raises(ValueError) as exc_info:
        validate_config_contract(config)
    assert "missing required keys" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()


def test_config_has_statutory_minimum_wage():
    """Config provides statutory minimum wage (minimum_wage.hourly_rate)."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "minimum_wage" in config
    assert "hourly_rate" in config["minimum_wage"]
    assert config["minimum_wage"]["hourly_rate"] > 0


def test_config_has_usc_thresholds():
    """Config provides usc_exemption_threshold / usc_threshold (usc.exemption_limit)."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "usc" in config
    assert "exemption_limit" in config["usc"]


def test_config_has_valid_prsi_classes():
    """Config provides valid_prsi_classes."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "prsi" in config
    assert "valid_prsi_classes" in config["prsi"]
    assert isinstance(config["prsi"]["valid_prsi_classes"], list)
    assert len(config["prsi"]["valid_prsi_classes"]) > 0


def test_config_has_weekly_threshold_lower():
    """Config provides weekly_threshold_lower (prsi.class_a.weekly_threshold_lower)."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config.get("prsi", {}).get("class_a", {}).get("weekly_threshold_lower") is not None


def test_config_has_minimum_contribution_rate():
    """Config provides minimum_contribution_rate for auto-enrolment."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config.get("auto_enrolment", {}).get("eligibility", {}).get("minimum_contribution_rate") is not None


def test_config_has_auto_enrolment_earnings_threshold():
    """Config provides auto_enrolment_earnings_threshold (annual_earnings_min)."""
    config = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config.get("auto_enrolment", {}).get("eligibility", {}).get("annual_earnings_min") is not None
