"""
IE-2026.01 config contract validation.
Raises clear errors if required keys are missing. Used at load time or in tests.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple


# Required paths: (path_components, human_name for error)
# Path is dotted or nested: ("minimum_wage", "hourly_rate") -> config["minimum_wage"]["hourly_rate"]
REQUIRED_CONFIG_PATHS: List[Tuple[Tuple[str, ...], str]] = [
    (("minimum_wage", "hourly_rate"), "statutory_minimum_wage (minimum_wage.hourly_rate)"),
    (("usc", "exemption_limit"), "usc_exemption_threshold (usc.exemption_limit)"),
    (("usc", "exemption_limit"), "usc_threshold (usc.exemption_limit)"),
    (("prsi", "valid_prsi_classes"), "valid_prsi_classes (prsi.valid_prsi_classes)"),
    (("prsi", "class_a", "weekly_threshold_lower"), "weekly_threshold_lower (prsi.class_a.weekly_threshold_lower)"),
    (("auto_enrolment", "eligibility", "minimum_contribution_rate"), "minimum_contribution_rate (auto_enrolment.eligibility.minimum_contribution_rate)"),
    (("auto_enrolment", "eligibility", "annual_earnings_min"), "auto_enrolment_earnings_threshold (auto_enrolment.eligibility.annual_earnings_min)"),
]


def _get_nested(config: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    current: Any = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def validate_config_contract(config: Dict[str, Any]) -> None:
    """
    Validate that config contains all required keys for IE-2026.01 rules.
    Raises ValueError with a clear message listing missing keys.
    """
    missing: List[str] = []
    seen_names: set = set()
    for path, name in REQUIRED_CONFIG_PATHS:
        if name in seen_names:
            continue
        seen_names.add(name)
        value = _get_nested(config, path)
        if value is None:
            missing.append(name)
    if missing:
        raise ValueError(
            f"Config contract violation: missing required keys: {', '.join(sorted(missing))}. "
            "Ensure ie_config_2026.json contains minimum_wage.hourly_rate, usc.exemption_limit, "
            "prsi.valid_prsi_classes, prsi.class_a.weekly_threshold_lower, "
            "auto_enrolment.eligibility.minimum_contribution_rate, auto_enrolment.eligibility.annual_earnings_min."
        )
