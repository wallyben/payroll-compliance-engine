from core.rules.rules import rule_paye_001_negative_or_impossible
from core.normalize.schema import CanonicalPayrollRow


def test_negative_paye_flags_ie_paye_001():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, paye=-10.0)
    findings = rule_paye_001_negative_or_impossible([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYE.001"


def test_paye_exceeds_gross_flags_ie_paye_001():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=100.0, paye=1100.0)
    findings = rule_paye_001_negative_or_impossible([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYE.001"


def test_valid_paye_does_not_flag_ie_paye_001():
    row = CanonicalPayrollRow(employee_id="E3", gross_pay=1000.0, net_pay=700.0, paye=200.0)
    findings = rule_paye_001_negative_or_impossible([row])
    assert findings == []
