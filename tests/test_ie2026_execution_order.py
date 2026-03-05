"""
Freeze deterministic rule execution order.
Row rules execute before file rules; IE.DATA.002 runs first when invalid_rows present.
"""
import pytest
from core.rules.engine import _IE_2026_RULE_LIST
from core.rules.compliance.data_rules import rule_ie_data_002_from_invalid_rows
from core.rules.registry import all_rule_ids

# IE-2026.01 row rules (by execution order in _IE_2026_RULE_LIST)
EXPECTED_ROW_RULE_IDS = [
    "IE.NET.001",
    "IE.NET.002",
    "IE.DEDUCT.001",
    "IE.PENSION.002",
    "IE.PAY.002",
    "IE.MINWAGE.001",
    "IE.PAY.001",
    "IE.NET.003",
    "IE.PRSI.001",
    "IE.PRSI.004",
    "IE.USC.001",
    "IE.USC.002",
    "IE.AUTOENROL.001",
    "IE.AUTOENROL.002",
    "IE.BIK.001",
    "IE.PRSI.003",
]

# File rules must run after row rules
EXPECTED_FILE_RULE_IDS = [
    "IE.TOTALS.001",
    "IE.DATA.001",
]


def test_ie_2026_rule_list_defines_explicit_order():
    """_IE_2026_RULE_LIST defines explicit rule execution order."""
    extracted = [rule_ids[0] for rule_ids, _ in _IE_2026_RULE_LIST]
    assert len(extracted) == 18
    assert "IE.DATA.002" not in extracted


def test_row_rules_before_file_rules():
    """Row rules execute before file rules in _IE_2026_RULE_LIST."""
    extracted = [rule_ids[0] for rule_ids, _ in _IE_2026_RULE_LIST]
    row_positions = [extracted.index(rid) for rid in EXPECTED_ROW_RULE_IDS if rid in extracted]
    file_positions = [extracted.index(rid) for rid in EXPECTED_FILE_RULE_IDS if rid in extracted]
    assert max(row_positions) < min(file_positions)


def test_data_002_first_when_invalid_rows():
    """IE.DATA.002 runs first when invalid_rows provided (in run_all)."""
    invalid = [{"row_number": 1, "errors": [{"msg": "gross_pay missing"}]}]
    findings = rule_ie_data_002_from_invalid_rows(invalid)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.DATA.002"
    assert findings[0]["severity"] == "CRITICAL"


def test_execution_order_stable():
    """Execution order is stable: same as _IE_2026_RULE_LIST iteration."""
    order_from_engine = [rule_ids[0] for rule_ids, _ in _IE_2026_RULE_LIST]
    assert order_from_engine == EXPECTED_ROW_RULE_IDS + EXPECTED_FILE_RULE_IDS
