from core.rules.rules import rule_payslip_002_gross_missing_or_zero
from core.normalize.schema import CanonicalPayrollRow


def test_gross_zero_flags_ie_payslip_002():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=0.0, net_pay=0.0)
    findings = rule_payslip_002_gross_missing_or_zero([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYSLIP.002"


def test_gross_positive_does_not_flag():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=800.0)
    findings = rule_payslip_002_gross_missing_or_zero([row])
    assert findings == []
