from core.rules.rules import rule_sanity_009_deductions_exceed_gross
from core.normalize.schema import CanonicalPayrollRow


def test_deductions_exceed_gross_flags_ie_sanity_009():
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=100.0, net_pay=-50.0,
        paye=80.0, usc=30.0, prsi_ee=25.0, pension_ee=15.0,
    )
    findings = rule_sanity_009_deductions_exceed_gross([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.009"


def test_deductions_below_gross_does_not_flag():
    row = CanonicalPayrollRow(
        employee_id="E2", gross_pay=1000.0, net_pay=700.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_009_deductions_exceed_gross([row])
    assert findings == []
