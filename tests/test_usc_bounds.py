from core.rules.rules import rule_usc_deterministic_bounds
from core.normalize.schema import CanonicalPayrollRow


def test_usc_negative_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=900.0,
        usc=-1.0
    )
    findings = rule_usc_deterministic_bounds([row], {})
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.USC.002"


def test_usc_exceeds_gross_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=900.0,
        usc=1200.0
    )
    findings = rule_usc_deterministic_bounds([row], {})
    assert len(findings) == 1


def test_usc_nonzero_with_zero_gross_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=0.0,
        net_pay=0.0,
        usc=10.0
    )
    findings = rule_usc_deterministic_bounds([row], {})
    assert len(findings) == 1


def test_usc_valid_passes():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=900.0,
        usc=50.0
    )
    findings = rule_usc_deterministic_bounds([row], {})
    assert findings == []
