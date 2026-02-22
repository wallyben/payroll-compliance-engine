from core.rules.rules import rule_usc_004_negative
from core.normalize.schema import CanonicalPayrollRow


def test_negative_usc_flags_ie_usc_004():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, usc=-10.0)
    findings = rule_usc_004_negative([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.USC.004"


def test_non_negative_usc_does_not_flag_ie_usc_004():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=950.0, usc=20.0)
    findings = rule_usc_004_negative([row])
    assert findings == []
