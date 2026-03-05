"""
Determinism: same payroll file run twice yields identical findings and exposure report.
"""
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from core.normalize.mapper import normalize
from core.rules.engine import run_all
from core.reporting.exposure_engine import build_exposure_report
from dataclasses import asdict

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "rules" / "ie_config_2026.json"


def _load_config():
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def test_same_file_twice_identical_findings_and_exposure():
    """Run same CSV twice; findings and exposure report must be identical."""
    csv = (
        "employee_id,gross_pay,net_pay,paye,usc,prsi_ee\n"
        "E1,1000,800,100,50,50\n"
        "E2,2000,1600,200,100,100\n"
        "E3,500,300,50,25,25\n"
    )
    df = pd.read_csv(io.StringIO(csv))
    mapping = {
        "employee_id": "employee_id",
        "gross_pay": "gross_pay",
        "net_pay": "net_pay",
        "paye": "paye",
        "usc": "usc",
        "prsi_ee": "prsi_ee",
    }
    config = _load_config()
    rows1, invalid1 = normalize(df, mapping)
    rows2, invalid2 = normalize(df, mapping)
    findings1 = run_all(rows1, config, invalid_rows=invalid1)
    findings2 = run_all(rows2, config, invalid_rows=invalid2)
    assert findings1 == findings2
    report1 = build_exposure_report(findings1)
    report2 = build_exposure_report(findings2)
    d1 = asdict(report1)
    d2 = asdict(report2)
    assert d1["underpayment_total"] == d2["underpayment_total"]
    assert d1["overpayment_total"] == d2["overpayment_total"]
    assert d1["employees_impacted"] == d2["employees_impacted"]
    assert d1["confidence_level"] == d2["confidence_level"]
    assert d1["total_exposure"] == d2["total_exposure"]
    assert d1["severity_counts"] == d2["severity_counts"]
    assert len(d1["categories"]) == len(d2["categories"])
    assert len(d1["rule_breakdown"]) == len(d2["rule_breakdown"])
