from core.rules.rules import rule_prsi_004_applied_below_threshold
from core.normalize.schema import CanonicalPayrollRow


def test_prsi_deducted_below_threshold_flags_ie_prsi_004():
    # Weekly threshold 352 -> no PRSI below that; gross 300 with prsi_ee 10 is wrong
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=300.0, net_pay=290.0, prsi_ee=10.0)
    cfg = {"prsi": {"class_a": {"weekly_threshold_lower": 352}}}
    findings = rule_prsi_004_applied_below_threshold([row], cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.004"


def test_prsi_zero_below_threshold_does_not_flag_ie_prsi_004():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=300.0, net_pay=300.0, prsi_ee=0.0)
    cfg = {"prsi": {"class_a": {"weekly_threshold_lower": 352}}}
    findings = rule_prsi_004_applied_below_threshold([row], cfg)
    assert findings == []
