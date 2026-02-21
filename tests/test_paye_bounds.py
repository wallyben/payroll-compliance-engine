from core.rules.rules import rule_paye_deterministic_bounds
from core.normalize.schema import CanonicalPayrollRow


def test_paye_negative_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=800.0,
        paye=-1.0
    )

    findings = rule_paye_deterministic_bounds([row], {"income_tax": {"higher_rate": 0.4}})
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYE.002"


def test_paye_exceeds_gross_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=800.0,
        paye=1500.0
    )

    findings = rule_paye_deterministic_bounds([row], {"income_tax": {"higher_rate": 0.4}})
    assert len(findings) == 1


def test_paye_exceeds_higher_rate_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=800.0,
        paye=500.0  # > 40%
    )

    findings = rule_paye_deterministic_bounds([row], {"income_tax": {"higher_rate": 0.4}})
    assert len(findings) == 1


def test_paye_valid_passes():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,
        net_pay=800.0,
        paye=400.0
    )

    findings = rule_paye_deterministic_bounds([row], {"income_tax": {"higher_rate": 0.4}})
    assert findings == []
