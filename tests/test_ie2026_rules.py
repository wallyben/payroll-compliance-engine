"""Tests for IE-2026.01 rule detection and false positives."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import date

import pytest
from core.normalize.schema import CanonicalPayrollRow
from core.rules.arithmetic.row_rules import (
    rule_ie_net_001,
    rule_ie_net_002,
    rule_ie_deduct_001,
    rule_ie_pension_002,
    rule_ie_pay_002,
)
from core.rules.arithmetic.file_rules import rule_ie_totals_001
from core.rules.operational.row_rules import (
    rule_ie_minwage_001,
    rule_ie_pay_001,
    rule_ie_net_003,
    rule_ie_prsi_001,
    rule_ie_prsi_004,
)
from core.rules.operational.file_rules import rule_ie_data_001
from core.rules.compliance.row_rules import (
    rule_ie_usc_001,
    rule_ie_usc_002,
    rule_ie_autoenrol_001,
    rule_ie_autoenrol_002,
    rule_ie_bik_001,
    rule_ie_prsi_003,
)
from core.rules.compliance.data_rules import rule_ie_data_002_from_invalid_rows

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "rules" / "ie_config_2026.json"


def _load_config():
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _row(**kw):
    defaults = {"employee_id": "E1", "gross_pay": 1000.0, "net_pay": 800.0}
    defaults.update(kw)
    return CanonicalPayrollRow(**defaults)


# ---- IE.NET.001 ----
def test_ie_net_001_flags_net_gt_gross():
    rows = [_row(net_pay=1100.0, gross_pay=1000.0)]
    findings = rule_ie_net_001(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.NET.001"
    assert findings[0]["severity"] == "CRITICAL"
    assert "E1" in findings[0]["employee_refs"]


def test_ie_net_001_no_false_positive():
    rows = [_row(net_pay=800.0, gross_pay=1000.0)]
    assert len(rule_ie_net_001(rows)) == 0


# ---- IE.NET.002 ----
def test_ie_net_002_flags_negative_net():
    rows = [_row(net_pay=-50.0)]
    findings = rule_ie_net_002(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.NET.002"
    assert findings[0]["severity"] == "CRITICAL"


def test_ie_net_002_no_false_positive():
    rows = [_row(net_pay=0.0), _row(employee_id="E2", gross_pay=500.0, net_pay=400.0)]
    assert len(rule_ie_net_002(rows)) == 0


# ---- IE.DEDUCT.001 ----
def test_ie_deduct_001_flags_deductions_gt_gross():
    rows = [_row(gross_pay=1000.0, net_pay=0.0, total_deductions=1200.0)]
    findings = rule_ie_deduct_001(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.DEDUCT.001"
    assert findings[0]["severity"] == "HIGH"


def test_ie_deduct_001_derives_from_paye_usc_prsi_pension():
    rows = [_row(gross_pay=100.0, paye=50.0, usc=20.0, prsi_ee=10.0, pension_ee=30.0)]
    findings = rule_ie_deduct_001(rows)
    assert len(findings) == 1
    assert 110.0 > 100.0


def test_ie_deduct_001_no_false_positive():
    rows = [_row(gross_pay=1000.0, total_deductions=300.0)]
    assert len(rule_ie_deduct_001(rows)) == 0


# ---- IE.PENSION.002 ----
def test_ie_pension_002_flags_pension_over_50_percent():
    rows = [_row(gross_pay=1000.0, pension_ee=400.0, pension_er=200.0)]
    findings = rule_ie_pension_002(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PENSION.002"
    assert findings[0]["severity"] == "MEDIUM"


def test_ie_pension_002_no_false_positive():
    rows = [_row(gross_pay=1000.0, pension_ee=200.0, pension_er=200.0)]
    assert len(rule_ie_pension_002(rows)) == 0


# ---- IE.PAY.002 ----
def test_ie_pay_002_flags_rate_gt_250():
    rows = [_row(gross_pay=3000.0, hours=10.0)]
    findings = rule_ie_pay_002(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAY.002"
    assert findings[0]["evidence"]["effective_rate"] == 300.0


def test_ie_pay_002_skips_zero_hours():
    rows = [_row(gross_pay=5000.0, hours=0.0)]
    assert len(rule_ie_pay_002(rows)) == 0


def test_ie_pay_002_no_false_positive():
    rows = [_row(gross_pay=1000.0, hours=10.0)]
    assert len(rule_ie_pay_002(rows)) == 0


# ---- IE.TOTALS.001 (file-level) ----
def test_ie_totals_001_flags_file_mismatch():
    rows = [
        _row(employee_id="E1", gross_pay=1000.0, net_pay=999.0, paye=0.0, usc=0.0, prsi_ee=0.0),
        _row(employee_id="E2", gross_pay=1000.0, net_pay=999.0, paye=0.0, usc=0.0, prsi_ee=0.0),
    ]
    findings = rule_ie_totals_001(rows, tolerance=0.02)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.TOTALS.001"
    assert findings[0]["severity"] == "CRITICAL"


def test_ie_totals_001_clean_passes():
    rows = [
        _row(employee_id="E1", gross_pay=1000.0, net_pay=800.0, paye=100.0, usc=50.0, prsi_ee=50.0),
        _row(employee_id="E2", gross_pay=1000.0, net_pay=800.0, paye=100.0, usc=50.0, prsi_ee=50.0),
    ]
    findings = rule_ie_totals_001(rows, tolerance=0.02)
    assert len(findings) == 0


# ---- IE.MINWAGE.001 ----
def test_ie_minwage_001_flags_below_minimum():
    cfg = _load_config()
    rows = [_row(gross_pay=50.0, hours=5.0)]
    findings = rule_ie_minwage_001(rows, cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.MINWAGE.001"
    assert findings[0]["severity"] == "HIGH"


def test_ie_minwage_001_no_false_positive():
    cfg = _load_config()
    rows = [_row(gross_pay=200.0, hours=10.0)]
    assert len(rule_ie_minwage_001(rows, cfg)) == 0


# ---- IE.PAY.001 ----
def test_ie_pay_001_flags_hours_no_gross():
    rows = [_row(gross_pay=0.0, net_pay=0.0, hours=40.0)]
    findings = rule_ie_pay_001(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAY.001"


def test_ie_pay_001_no_false_positive():
    rows = [_row(gross_pay=1000.0, hours=40.0)]
    assert len(rule_ie_pay_001(rows)) == 0


# ---- IE.NET.003 ----
def test_ie_net_003_flags_gross_positive_net_zero():
    rows = [_row(gross_pay=1000.0, net_pay=0.0)]
    findings = rule_ie_net_003(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.NET.003"


def test_ie_net_003_no_false_positive():
    rows = [_row(gross_pay=1000.0, net_pay=800.0)]
    assert len(rule_ie_net_003(rows)) == 0


# ---- IE.DATA.001 (duplicate) ----
def test_ie_data_001_flags_duplicate_employee():
    rows = [
        _row(employee_id="E1", gross_pay=1000.0, net_pay=800.0),
        _row(employee_id="E1", gross_pay=1000.0, net_pay=800.0),
        _row(employee_id="E2", gross_pay=500.0, net_pay=400.0),
    ]
    findings = rule_ie_data_001(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.DATA.001"
    assert "E1" in findings[0]["employee_refs"]


def test_ie_data_001_no_duplicate_passes():
    rows = [_row(employee_id="E1"), _row(employee_id="E2", gross_pay=500.0, net_pay=400.0)]
    assert len(rule_ie_data_001(rows)) == 0


# ---- IE.PRSI.001 ----
def test_ie_prsi_001_flags_missing_prsi_class():
    rows = [_row(prsi_class=None)]
    findings = rule_ie_prsi_001(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.001"


def test_ie_prsi_001_no_false_positive():
    rows = [_row(prsi_class="A")]
    assert len(rule_ie_prsi_001(rows)) == 0


# ---- IE.PRSI.004 ----
def test_ie_prsi_004_flags_invalid_class():
    cfg = _load_config()
    rows = [_row(prsi_class="X")]
    findings = rule_ie_prsi_004(rows, cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.004"


def test_ie_prsi_004_no_false_positive():
    cfg = _load_config()
    rows = [_row(prsi_class="A")]
    assert len(rule_ie_prsi_004(rows, cfg)) == 0


# ---- IE.USC.001 ----
def test_ie_usc_001_flags_usc_below_exemption():
    cfg = _load_config()
    rows = [_row(gross_pay=200.0, usc=10.0)]
    findings = rule_ie_usc_001(rows, cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.USC.001"


def test_ie_usc_001_no_false_positive():
    cfg = _load_config()
    rows = [_row(gross_pay=200.0, usc=0.0)]
    assert len(rule_ie_usc_001(rows, cfg)) == 0


# ---- IE.USC.002 ----
def test_ie_usc_002_flags_usc_zero_above_threshold():
    cfg = _load_config()
    rows = [_row(gross_pay=3000.0, usc=0.0)]
    findings = rule_ie_usc_002(rows, cfg)
    assert len(findings) >= 1
    assert findings[0]["rule_id"] == "IE.USC.002"


# ---- IE.AUTOENROL.001 ----
def test_ie_autoenrol_001_eligible_no_pension():
    cfg = _load_config()
    rows = [_row(gross_pay=2000.0, age=30, pension_ee=0.0, pension_er=0.0)]
    findings = rule_ie_autoenrol_001(rows, cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.AUTOENROL.001"


def test_ie_autoenrol_001_skips_when_age_missing():
    cfg = _load_config()
    rows = [_row(gross_pay=2000.0, age=None, pension_ee=0.0)]
    assert len(rule_ie_autoenrol_001(rows, cfg)) == 0


# ---- IE.BIK.001 ----
def test_ie_bik_001_flags_car_allowance_zero_bik():
    rows = [_row(allowance_type="car", bik_value=0.0)]
    findings = rule_ie_bik_001(rows)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.BIK.001"


def test_ie_bik_001_no_false_positive():
    rows = [_row(allowance_type="car", bik_value=500.0)]
    assert len(rule_ie_bik_001(rows)) == 0


# ---- IE.PRSI.003 ----
def test_ie_prsi_003_flags_class_a_below_threshold():
    cfg = _load_config()
    rows = [_row(prsi_class="A", weekly_earnings=300.0)]
    findings = rule_ie_prsi_003(rows, cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.003"
    assert findings[0]["severity"] == "LOW"


def test_ie_prsi_003_no_false_positive():
    cfg = _load_config()
    rows = [_row(prsi_class="A", weekly_earnings=400.0)]
    assert len(rule_ie_prsi_003(rows, cfg)) == 0


# ---- IE.DATA.002 (invalid rows) ----
def test_ie_data_002_from_invalid_rows():
    invalid = [
        {"row_number": 1, "errors": [{"msg": "employee_id required"}]},
        {"row_number": 2, "errors": [{"msg": "gross_pay missing"}]},
    ]
    findings = rule_ie_data_002_from_invalid_rows(invalid)
    assert len(findings) == 2
    assert all(f["rule_id"] == "IE.DATA.002" for f in findings)
    assert all(f["severity"] == "CRITICAL" for f in findings)


def test_ie_data_002_empty_invalid():
    assert len(rule_ie_data_002_from_invalid_rows([])) == 0
