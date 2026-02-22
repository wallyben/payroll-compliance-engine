from core.rules.rules import rule_paye_003_zero_when_taxable_present
from core.normalize.schema import CanonicalPayrollRow


def test_paye_zero_above_band_flags_ie_paye_003():
    # standard_rate_band_single 44000 -> monthly ~3667; gross 4000 with zero PAYE is suspicious
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=4000.0, net_pay=3200.0, paye=0.0)
    cfg = {"income_tax": {"standard_rate_band_single": 44000}}
    findings = rule_paye_003_zero_when_taxable_present([row], cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PAYE.003"


def test_paye_non_zero_does_not_flag_ie_paye_003():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=4000.0, net_pay=3000.0, paye=400.0)
    cfg = {"income_tax": {"standard_rate_band_single": 44000}}
    findings = rule_paye_003_zero_when_taxable_present([row], cfg)
    assert findings == []
