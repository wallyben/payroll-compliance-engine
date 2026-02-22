from core.rules.rules import rule_sanity_008_net_equals_gross_with_deductions
from core.normalize.schema import CanonicalPayrollRow


def test_net_equals_gross_but_deductions_present_flags_ie_sanity_008():
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=1000.0, net_pay=1000.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_008_net_equals_gross_with_deductions([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.008"


def test_net_less_than_gross_does_not_flag():
    row = CanonicalPayrollRow(
        employee_id="E2", gross_pay=1000.0, net_pay=788.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_008_net_equals_gross_with_deductions([row])
    assert findings == []
