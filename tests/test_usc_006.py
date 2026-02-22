from core.rules.rules import rule_usc_006_missing_above_threshold
from core.normalize.schema import CanonicalPayrollRow


def test_usc_zero_above_exemption_flags_ie_usc_006():
    # exemption 13000 -> monthly ~1083; gross 2000/month = 24k annual > 13k, zero USC is wrong
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=2000.0, net_pay=1800.0, usc=0.0)
    cfg = {"usc": {"exemption_limit": 13000, "bands": []}}
    findings = rule_usc_006_missing_above_threshold([row], cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.USC.006"


def test_usc_non_zero_above_exemption_does_not_flag_ie_usc_006():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=2000.0, net_pay=1850.0, usc=30.0)
    cfg = {"usc": {"exemption_limit": 13000, "bands": []}}
    findings = rule_usc_006_missing_above_threshold([row], cfg)
    assert findings == []
