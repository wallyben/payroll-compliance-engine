from core.rules.engine import run_all
from core.normalize.schema import CanonicalPayrollRow

BASE_CFG = {
    "usc": {"exemption_limit": 13000, "bands": [{"cap": 12012, "rate": 0.005}, {"cap": 28700, "rate": 0.02}, {"cap": 70044, "rate": 0.03}, {"cap": None, "rate": 0.08}]},
    "income_tax": {"standard_rate_band_single": 44000, "standard_rate": 0.2, "higher_rate": 0.4},
    "prsi": {"class_a": {"employee_rate_pre_2026_10_01": 0.042, "employer_rate_higher": 0.114, "employer_rate_lower": 0.0915, "employee_rate_from_2026_10_01": 0.0435, "weekly_threshold_for_higher": 552}},
    "minimum_wage": {"hourly_rate": 12.70},
    "auto_enrolment": {"eligibility": {"annual_earnings_min": 20000}},
}

def rule_ids(findings):
    return {f["rule_id"] for f in findings}

def test_regression_prsi_deterministic_breach():
    row = CanonicalPayrollRow(employee_id="A", gross_pay=1000.0, net_pay=900.0, prsi_ee=100.0, prsi_er=200.0)
    findings = run_all([row], BASE_CFG)
    assert "IE.PRSI.002" in rule_ids(findings)

def test_regression_usc_deterministic_breach():
    row = CanonicalPayrollRow(employee_id="B", gross_pay=1000.0, net_pay=900.0, usc=1200.0)
    findings = run_all([row], BASE_CFG)
    assert "IE.USC.002" in rule_ids(findings)

def test_regression_net_upper_bound_breach():
    row = CanonicalPayrollRow(employee_id="C", gross_pay=1000.0, net_pay=800.0, paye=200.0, usc=50.0, prsi_ee=42.0, pension_ee=20.0)
    findings = run_all([row], BASE_CFG)
    assert "IE.NET.002" in rule_ids(findings)

def test_regression_paye_bounds_breach():
    row = CanonicalPayrollRow(employee_id="D", gross_pay=1000.0, net_pay=900.0, paye=500.0)
    findings = run_all([row], BASE_CFG)
    assert "IE.PAYE.002" in rule_ids(findings)

def test_regression_min_wage_breach():
    row = CanonicalPayrollRow(employee_id="E", gross_pay=100.0, net_pay=90.0, hours=10.0)
    findings = run_all([row], BASE_CFG)
    assert "IE.MINWAGE.001" in rule_ids(findings)

def test_regression_auto_enrolment_breach():
    row = CanonicalPayrollRow(employee_id="F", gross_pay=1000.0, net_pay=900.0, pension_ee=50.0)
    findings = run_all([row], BASE_CFG)
    assert "IE.AUTOENROL.001" in rule_ids(findings)
