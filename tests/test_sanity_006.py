from core.rules.rules import rule_sanity_006_net_inconsistency
from core.normalize.schema import CanonicalPayrollRow


def test_net_not_equal_gross_minus_deductions_flags_ie_sanity_006():
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=1000.0, net_pay=600.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    # expected net = 1000 - 212 = 788; 600 != 788
    findings = rule_sanity_006_net_inconsistency([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.006"


def test_net_equals_gross_minus_deductions_does_not_flag():
    row = CanonicalPayrollRow(
        employee_id="E2", gross_pay=1000.0, net_pay=788.0,
        paye=100.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0,
    )
    findings = rule_sanity_006_net_inconsistency([row])
    assert findings == []
