"""Deterministic config path resolution. No CWD-relative paths."""

import json
from pathlib import Path

# Project root: this file is apps/api/config_loader.py -> parent.parent.parent = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RULES_CONFIG_PATH = _PROJECT_ROOT / "core" / "rules" / "ie_config_2026.json"


def load_rules_config() -> dict:
    """Load rules config from deterministic path."""
    return json.loads(RULES_CONFIG_PATH.read_text(encoding="utf-8"))
