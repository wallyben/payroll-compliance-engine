from core.rules.rules import rule_net_deterministic_upper_bound
from core.normalize.schema import CanonicalPayrollRow


def test_net_exceeds_gross_minus_known_deductions_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=800.0,
        paye=200.0,
        usc=50.0,
        prsi_ee=42.0,
        pension_ee=20.0,
    )
    # max_possible_net = 1000 - (200+50+42+20) = 688
    findings = rule_net_deterministic_upper_bound([row], {})
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.NET.002"


def test_net_below_gross_minus_known_deductions_ok():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=600.0,  # could be other deductions
        paye=200.0,
        usc=50.0,
        prsi_ee=42.0,
        pension_ee=20.0,
    )
    findings = rule_net_deterministic_upper_bound([row], {})
    assert findings == []


def test_net_equal_to_gross_minus_known_deductions_ok():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=688.0,
        paye=200.0,
        usc=50.0,
        prsi_ee=42.0,
        pension_ee=20.0,
    )
    findings = rule_net_deterministic_upper_bound([row], {})
    assert findings == []


def test_net_with_zero_deductions_ok():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=950.0,
        paye=0.0,
        usc=0.0,
        prsi_ee=0.0,
        pension_ee=0.0,
    )
    findings = rule_net_deterministic_upper_bound([row], {})
    assert findings == []
