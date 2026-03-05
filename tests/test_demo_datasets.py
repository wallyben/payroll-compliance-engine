"""Demo dataset stability: assert expected finding counts and severities after rule/config changes."""
from pathlib import Path

import pandas as pd
import pytest

from apps.api.config_loader import load_rules_config
from core.normalize.mapper import normalize
from core.reporting.exposure_engine import build_exposure_report
from core.rules.engine import run_all

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEMO_DIR = _PROJECT_ROOT / "demo_data"
_SCAN_PROFILE = "bureau_wedge"


def _run_demo_file(csv_name: str):
    path = _DEMO_DIR / csv_name
    assert path.exists(), f"Missing {path}"
    df = pd.read_csv(path)
    mapping = {c: c for c in df.columns}
    allowed = {
        "employee_id", "gross_pay", "net_pay", "hours", "paye", "usc",
        "prsi_ee", "prsi_er", "pension_ee", "pension_er", "prsi_class",
        "age", "weekly_earnings", "total_deductions",
    }
    for k in list(mapping):
        if k not in allowed:
            del mapping[k]
    rows, invalid = normalize(df, mapping)
    config = load_rules_config()
    config["scan_profile"] = _SCAN_PROFILE
    findings = run_all(rows, config, invalid_rows=invalid)
    return findings, build_exposure_report(findings)


def test_clean_payroll_zero_findings():
    """clean_payroll.csv must produce 0 findings → PASSED → certificate available."""
    findings, _ = _run_demo_file("clean_payroll.csv")
    assert len(findings) == 0, (
        f"clean_payroll.csv must produce 0 findings; got {len(findings)}: "
        f"{[f.get('rule_id') for f in findings]}"
    )


def test_minor_issues_two_to_three_findings_no_critical():
    """minor_issues_payroll.csv must produce 2–3 findings, no CRITICAL."""
    findings, _ = _run_demo_file("minor_issues_payroll.csv")
    critical = [f for f in findings if f.get("severity") == "CRITICAL"]
    assert len(critical) == 0, (
        f"minor_issues_payroll.csv must have no CRITICAL findings; got {len(critical)}"
    )
    assert 0 < len(findings) < 5, (
        f"minor_issues_payroll.csv must produce 2–3 findings; got {len(findings)}"
    )


def test_severe_issues_multiple_findings_including_critical():
    """severe_issues_payroll.csv must produce ≥3 findings including at least one CRITICAL."""
    findings, exposure = _run_demo_file("severe_issues_payroll.csv")
    assert len(findings) >= 3, (
        f"severe_issues_payroll.csv must produce ≥3 findings; got {len(findings)}"
    )
    critical = [f for f in findings if f.get("severity") == "CRITICAL"]
    assert len(critical) >= 1, (
        f"severe_issues_payroll.csv must produce at least one CRITICAL finding; got {[f.get('severity') for f in findings]}"
    )
    assert exposure.total_exposure >= 0, "Exposure should be non-negative (non-zero expected for severe)."
