"""
CLI smoke test: validate_payroll.py runs and prints summary.
"""
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CLI_SCRIPT = _PROJECT_ROOT / "cli" / "validate_payroll.py"
_SAMPLE_CSV = _PROJECT_ROOT / "phase1_test_files" / "01_clean.csv"


def test_cli_script_exists():
    assert _CLI_SCRIPT.is_file()


def test_cli_runs_on_sample_csv():
    """Run validate_payroll.py on a sample CSV; exit code 0 and output contains Ruleset and Employees."""
    result = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), str(_SAMPLE_CSV)],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
        timeout=10,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Ruleset:" in result.stdout
    assert "IE-2026.01" in result.stdout
    assert "Employees processed:" in result.stdout
    assert "Findings:" in result.stdout
    assert "CRITICAL:" in result.stdout
    assert "HIGH:" in result.stdout
    assert "MEDIUM:" in result.stdout
    assert "LOW:" in result.stdout


def test_cli_missing_file_exits_non_zero():
    result = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), "nonexistent.csv"],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
        timeout=5,
    )
    assert result.returncode != 0
    assert "not found" in result.stderr or "File" in result.stderr
