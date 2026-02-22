from core.rules.rules import rule_prsi_deterministic_bounds
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


def test_prsi_exceeds_gross_flags_ie_prsi_002():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, prsi_ee=500.0, prsi_er=200.0)
    findings = rule_prsi_deterministic_bounds([row], BASE_CFG)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.002"


def test_prsi_within_bounds_does_not_flag_ie_prsi_002():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=844.0, prsi_ee=42.0, prsi_er=91.5)
    findings = rule_prsi_deterministic_bounds([row], BASE_CFG)
    assert findings == []
