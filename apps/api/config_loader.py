"""Deterministic config path resolution. No CWD-relative paths."""

import json
from pathlib import Path

# Project root: this file is apps/api/config_loader.py -> parent.parent.parent = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

RULES_CONFIG_PATH = _PROJECT_ROOT / "core" / "rules" / "ie_config_2026.json"

# Validated report directory (deterministic, under project root)
REPORTS_DIR = (_PROJECT_ROOT / "storage" / "reports").resolve()


def load_rules_config() -> dict:
    """Load rules config from deterministic path."""
    return json.loads(RULES_CONFIG_PATH.read_text(encoding="utf-8"))


def report_path_for_run(run_id: int) -> Path:
    """Path to report PDF for a run. Validates result is under REPORTS_DIR."""
    path = (REPORTS_DIR / f"run_{run_id}.pdf").resolve()
    if not path.is_relative_to(REPORTS_DIR):
        raise ValueError("report path would escape reports directory")
    return path
