from core.rules.rules import rule_sanity_005_negative_net
from core.normalize.schema import CanonicalPayrollRow


def test_negative_net_pay_flags_ie_sanity_005():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=-50.0)
    findings = rule_sanity_005_negative_net([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.005"


def test_non_negative_net_pay_does_not_flag_ie_sanity_005():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=700.0)
    findings = rule_sanity_005_negative_net([row])
    assert findings == []
