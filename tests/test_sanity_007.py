from core.rules.rules import rule_sanity_007_net_upper_bound
from core.normalize.schema import CanonicalPayrollRow


def test_net_exceeds_gross_minus_deductions_flags_ie_sanity_007():
    # gross 1000 - (100+50+42+20) = 788 max net; net 800 is invalid
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=1000.0, net_pay=800.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_007_net_upper_bound([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.007"


def test_net_below_gross_minus_deductions_does_not_flag():
    row = CanonicalPayrollRow(
        employee_id="E2", gross_pay=1000.0, net_pay=700.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_007_net_upper_bound([row])
    assert findings == []
