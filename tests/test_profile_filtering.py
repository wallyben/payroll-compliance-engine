import json
from pathlib import Path

from core.rules.engine import run_all
from core.normalize.schema import CanonicalPayrollRow


def test_profile_filters_rules():
    profile_path = Path("config/scan_profiles/bureau_wedge.json")
    profile = json.loads(profile_path.read_text())
    wedge_rule_ids = set(profile["active_rules"])

    row = CanonicalPayrollRow(
        employee_id="T1",
        gross_pay=1000.0,
        net_pay=1000.0
    )

    config = {
        "scan_profile": "BUREAU_WEDGE",
        "prsi": {
            "class_a": {
                "employee_rate_pre_2026_10_01": 0.04,
                "employer_rate_higher": 0.111,
                "weekly_threshold_lower": 352.01
            }
        },
        "usc": {
            "exemption_threshold": 13000
        },
        "income_tax": {
            "standard_rate_band_single": 42000
        }
    }

    findings = run_all([row], config)

    for f in findings:
        assert f["rule_id"] in wedge_rule_ids
