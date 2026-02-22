from core.rules.rules import rule_prsi_005_missing_above_threshold
from core.normalize.schema import CanonicalPayrollRow


def test_prsi_zero_above_threshold_flags_ie_prsi_005():
    # Weekly threshold 352; gross 500 with zero PRSI is wrong
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=500.0, net_pay=500.0, prsi_ee=0.0)
    cfg = {"prsi": {"class_a": {"weekly_threshold_lower": 352}}}
    findings = rule_prsi_005_missing_above_threshold([row], cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.005"


def test_prsi_non_zero_above_threshold_does_not_flag_ie_prsi_005():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=500.0, net_pay=479.0, prsi_ee=21.0)
    cfg = {"prsi": {"class_a": {"weekly_threshold_lower": 352}}}
    findings = rule_prsi_005_missing_above_threshold([row], cfg)
    assert findings == []
