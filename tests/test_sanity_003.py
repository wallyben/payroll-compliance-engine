from core.rules.rules import rule_sanity_003_impossible_or_negative_deductions
from core.normalize.schema import CanonicalPayrollRow


def test_negative_paye_flags_ie_sanity_003():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, paye=-50.0)
    findings = rule_sanity_003_impossible_or_negative_deductions([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.003"


def test_negative_usc_flags_ie_sanity_003():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=900.0, usc=-10.0)
    findings = rule_sanity_003_impossible_or_negative_deductions([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.003"


def test_non_negative_deductions_do_not_flag_ie_sanity_003():
    row = CanonicalPayrollRow(employee_id="E3", gross_pay=1000.0, net_pay=700.0, paye=100.0, usc=50.0, prsi_ee=42.0)
    findings = rule_sanity_003_impossible_or_negative_deductions([row])
    assert findings == []
