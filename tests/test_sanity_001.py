from core.rules.rules import rule_sanity_001_gross_deduction_consistency
from core.normalize.schema import CanonicalPayrollRow


def test_gross_minus_deductions_mismatch_net_flags_ie_sanity_001():
    # gross 1000 - (100+50+42+20) = 788, but net 700
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=1000.0, net_pay=700.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_001_gross_deduction_consistency([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.001"


def test_gross_minus_deductions_equals_net_does_not_flag_ie_sanity_001():
    row = CanonicalPayrollRow(
        employee_id="E2", gross_pay=1000.0, net_pay=788.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_001_gross_deduction_consistency([row])
    assert findings == []
