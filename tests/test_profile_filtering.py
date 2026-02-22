import json
from pathlib import Path

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


def test_profile_filters_rules():
    profile_path = Path("config/scan_profiles/bureau_wedge.json")
    profile = json.loads(profile_path.read_text())
    wedge_rule_ids = set(profile["active_rules"])

    row = CanonicalPayrollRow(
        employee_id="T1",
        gross_pay=1000.0,
        net_pay=1000.0
    )

    config = {**BASE_CFG, "scan_profile": "bureau_wedge"}
    findings = run_all([row], config)

    for f in findings:
        assert f["rule_id"] in wedge_rule_ids
