"""Minimal unit test for profile-based rule filtering."""
from core.rules.engine import run_all
from core.normalize.schema import CanonicalPayrollRow

BASE_CFG = {
    "usc": {"exemption_limit": 13000, "bands": [{"cap": 12012, "rate": 0.005}, {"cap": None, "rate": 0.08}]},
    "income_tax": {"standard_rate_band_single": 44000, "higher_rate": 0.4},
    "prsi": {
        "class_a": {
            "employee_rate_pre_2026_10_01": 0.042,
            "employer_rate_higher": 0.114,
            "employer_rate_lower": 0.0915,
            "weekly_threshold_for_higher": 552,
            "weekly_threshold_lower": 352,
        }
    },
    "minimum_wage": {"hourly_rate": 12.70},
    "auto_enrolment": {"eligibility": {"annual_earnings_min": 20000}},
}


def test_profile_filters_to_active_rules_only():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=0.0, net_pay=0.0)
    config_with_profile = {**BASE_CFG, "scan_profile": "test_filter"}
    findings = run_all([row], config_with_profile)
    rule_ids = {f["rule_id"] for f in findings}
    assert rule_ids == {"IE.SANITY.002"}, f"Expected only IE.SANITY.002, got {rule_ids}"
    assert len(findings) >= 1


def test_no_profile_runs_all_rules():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=0.0, net_pay=0.0)
    findings = run_all([row], BASE_CFG)
    rule_ids = {f["rule_id"] for f in findings}
    assert "IE.SANITY.002" in rule_ids
    assert len(rule_ids) >= 2
