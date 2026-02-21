from core.rules.rules import rule_auto_enrolment_deterministic
from core.normalize.schema import CanonicalPayrollRow


def test_auto_enrolment_breach_flags():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=1000.0,   # 12,000 annualised
        net_pay=900.0,
        pension_ee=50.0
    )

    cfg = {
        "auto_enrolment": {
            "eligibility": {
                "annual_earnings_min": 20000
            }
        }
    }

    findings = rule_auto_enrolment_deterministic([row], cfg)
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.AUTOENROL.001"


def test_auto_enrolment_valid_passes():
    row = CanonicalPayrollRow(
        employee_id="1",
        gross_pay=2500.0,  # 30,000 annualised
        net_pay=2000.0,
        pension_ee=50.0
    )

    cfg = {
        "auto_enrolment": {
            "eligibility": {
                "annual_earnings_min": 20000
            }
        }
    }

    findings = rule_auto_enrolment_deterministic([row], cfg)
    assert findings == []
