from core.rules.rules import rule_sanity_002_negative_or_zero_gross
from core.normalize.schema import CanonicalPayrollRow


def test_negative_or_zero_gross_pay_flags_ie_sanity_002():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=0.0, net_pay=0.0)
    findings = rule_sanity_002_negative_or_zero_gross([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.002"


def test_negative_gross_pay_flags_ie_sanity_002():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=-100.0, net_pay=-100.0)
    findings = rule_sanity_002_negative_or_zero_gross([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.002"


def test_positive_gross_pay_does_not_flag_ie_sanity_002():
    row = CanonicalPayrollRow(employee_id="E3", gross_pay=1000.0, net_pay=900.0)
    findings = rule_sanity_002_negative_or_zero_gross([row])
    assert findings == []
