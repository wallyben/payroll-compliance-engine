from core.rules.rules import rule_payslip_001_missing_itemised
from core.normalize.schema import CanonicalPayrollRow


def test_payslip_001_rule_exists():
    # CanonicalPayrollRow has no deduction_breakdown; rule is no-op until schema supports it
    findings = rule_payslip_001_missing_itemised([])
    assert findings == []
