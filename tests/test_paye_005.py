from core.rules.rules import rule_paye_005_applied_when_taxable_zero
from core.normalize.schema import CanonicalPayrollRow


def test_paye_positive_when_gross_zero_flags_ie_paye_005():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=0.0, net_pay=0.0, paye=50.0)
    findings = rule_paye_005_applied_when_taxable_zero([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYE.005"


def test_paye_zero_when_gross_zero_does_not_flag_ie_paye_005():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=0.0, net_pay=0.0, paye=0.0)
    findings = rule_paye_005_applied_when_taxable_zero([row])
    assert findings == []
