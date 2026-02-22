from core.rules.rules import rule_prsi_plausibility_class_a
from core.normalize.schema import CanonicalPayrollRow

BASE_CFG = {
    "prsi": {
        "class_a": {
            "employee_rate_pre_2026_10_01": 0.042,
            "employer_rate_higher": 0.114,
            "employer_rate_lower": 0.0915,
            "weekly_threshold_for_higher": 552,
        }
    },
}


def test_prsi_out_of_plausibility_band_flags_ie_prsi_001():
    # Expected EE at 4.2% of 1000 = 42; 200 is way outside 0.6*42..1.4*42
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=800.0, prsi_ee=200.0, prsi_er=114.0)
    findings = rule_prsi_plausibility_class_a([row], BASE_CFG)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.001"


def test_prsi_within_plausibility_does_not_flag_ie_prsi_001():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=958.0, prsi_ee=42.0, prsi_er=91.5)
    findings = rule_prsi_plausibility_class_a([row], BASE_CFG)
    assert findings == []
