from core.rules.rules import rule_prsi_003_negative
from core.normalize.schema import CanonicalPayrollRow


def test_negative_prsi_ee_flags_ie_prsi_003():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=900.0, prsi_ee=-15.0)
    findings = rule_prsi_003_negative([row])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.PRSI.003"


def test_non_negative_prsi_does_not_flag_ie_prsi_003():
    row = CanonicalPayrollRow(employee_id="E2", gross_pay=1000.0, net_pay=958.0, prsi_ee=42.0)
    findings = rule_prsi_003_negative([row])
    assert findings == []
