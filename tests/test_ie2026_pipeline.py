"""IE-2026.01 pipeline: normalize -> validate -> row rules -> file rules -> exposure."""
from __future__ import annotations
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from core.normalize.mapper import normalize
from core.rules.engine import run_all
from core.reporting.exposure_engine import build_exposure_report
from core.rules.registry import all_rule_ids
from core.rules.compliance.data_rules import rule_ie_data_002_from_invalid_rows

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "rules" / "ie_config_2026.json"


def _load_config():
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def test_pipeline_with_clean_csv_no_profile():
    csv = "employee_id,gross_pay,net_pay\nE1,1000,800\nE2,2000,1600\n"
    df = pd.read_csv(io.StringIO(csv))
    mapping = {"employee_id": "employee_id", "gross_pay": "gross_pay", "net_pay": "net_pay"}
    rows, invalid_rows = normalize(df, mapping)
    config = _load_config()
    findings = run_all(rows, config, invalid_rows=invalid_rows)
    report = build_exposure_report(findings)
    assert report.underpayment_total >= 0
    assert report.overpayment_total >= 0
    assert "total_exposure" in report.__dataclass_fields__
    assert "severity_counts" in report.__dataclass_fields__
    assert "rule_breakdown" in report.__dataclass_fields__


def test_pipeline_ie_data_002_when_invalid_rows():
    invalid = [
        {"row_number": 1, "errors": [{"msg": "employee_id required"}]},
        {"row_number": 2, "errors": [{"msg": "gross_pay missing"}]},
    ]
    findings = rule_ie_data_002_from_invalid_rows(invalid)
    assert len(findings) >= 1
    assert all(f["rule_id"] == "IE.DATA.002" for f in findings)
    assert all(f["severity"] == "CRITICAL" for f in findings)


def test_pipeline_deterministic_order():
    rule_ids = all_rule_ids()
    assert len(rule_ids) == 19
    assert len(rule_ids) == len(set(rule_ids))


def test_findings_include_rule_id_severity_message():
    from core.rules.arithmetic.row_rules import rule_ie_net_001
    from core.normalize.schema import CanonicalPayrollRow
    rows = [CanonicalPayrollRow(employee_id="E1", gross_pay=100.0, net_pay=150.0)]
    findings = rule_ie_net_001(rows)
    assert len(findings) == 1
    f = findings[0]
    assert "rule_id" in f
    assert "severity" in f
    assert "title" in f or "description" in f
    assert "amount_impact" in f
    assert "employee_refs" in f
