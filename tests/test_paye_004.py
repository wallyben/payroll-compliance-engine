from core.rules.rules import rule_paye_004_negative
from core.normalize.schema import CanonicalPayrollRow


def test_negative_paye_flags_ie_paye_004():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, paye=-20.0)
    findings = rule_paye_004_negative([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYE.004"


def test_non_negative_paye_does_not_flag_ie_paye_004():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=800.0, paye=100.0)
    findings = rule_paye_004_negative([row])
    assert findings == []
