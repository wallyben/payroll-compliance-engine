"""Phase 4 Gate 2: tests for core.reporting.exposure_engine."""
import pytest
from core.reporting.exposure_engine import (
    ExposureReport,
    ExposureCategoryBreakdown,
    build_exposure_report,
)


def test_clean_run():
    """No findings => zero totals, HIGH confidence, empty categories."""
    report = build_exposure_report([])
    assert isinstance(report, ExposureReport)
    assert report.underpayment_total == 0.0
    assert report.overpayment_total == 0.0
    assert report.categories == []
    assert report.employees_impacted == 0
    assert report.quantifiable_findings == 0
    assert report.non_quantifiable_findings == 0
    assert report.confidence_level == "HIGH"


def test_mixed_findings():
    """Quantifiable and non-quantifiable; under/over per category; distinct employees."""
    findings = [
        {
            "rule_id": "IE.PAYE.001",
            "severity": "HIGH",
            "title": "A",
            "description": "",
            "amount_impact": -100.0,
            "employee_refs": ["E1", "E2"],
        },
        {
            "rule_id": "IE.PAYE.001",
            "severity": "MEDIUM",
            "title": "B",
            "description": "",
            "amount_impact": 50.0,
            "employee_refs": ["E2", "E3"],
        },
        {
            "rule_id": "IE.PRSI.001",
            "severity": "LOW",
            "title": "C",
            "description": "",
            "amount_impact": None,
            "employee_refs": ["E1"],
        },
    ]
    report = build_exposure_report(findings)
    assert report.underpayment_total == 100.0
    assert report.overpayment_total == 50.0
    assert report.employees_impacted == 3  # E1, E2, E3
    assert report.quantifiable_findings == 2
    assert report.non_quantifiable_findings == 1
    # 1/3 > 20% => LOW
    assert report.confidence_level == "LOW"
    assert len(report.categories) == 2
    paye = next(c for c in report.categories if c.category == "IE.PAYE.001")
    assert paye.underpayment_total == 100.0
    assert paye.overpayment_total == 50.0
    assert paye.employees_impacted == 3
    assert paye.quantifiable_findings == 2
    assert paye.non_quantifiable_findings == 0
    prsi = next(c for c in report.categories if c.category == "IE.PRSI.001")
    assert prsi.underpayment_total == 0.0
    assert prsi.overpayment_total == 0.0
    assert prsi.employees_impacted == 1
    assert prsi.quantifiable_findings == 0
    assert prsi.non_quantifiable_findings == 1


def test_low_confidence_case():
    """>20% non-quantifiable => LOW confidence."""
    findings = [
        {"rule_id": "R1", "severity": "HIGH", "title": "T", "description": "", "amount_impact": 10.0, "employee_refs": []},
        {"rule_id": "R1", "severity": "HIGH", "title": "T", "description": "", "amount_impact": None, "employee_refs": []},
        {"rule_id": "R1", "severity": "HIGH", "title": "T", "description": "", "amount_impact": None, "employee_refs": []},
        {"rule_id": "R1", "severity": "HIGH", "title": "T", "description": "", "amount_impact": None, "employee_refs": []},
    ]
    report = build_exposure_report(findings)
    assert report.quantifiable_findings == 1
    assert report.non_quantifiable_findings == 3
    assert report.confidence_level == "LOW"


def test_stable_ordering():
    """Categories sorted by category name."""
    findings = [
        {"rule_id": "IE.USC.001", "severity": "HIGH", "title": "U", "description": "", "employee_refs": []},
        {"rule_id": "IE.PAYE.001", "severity": "HIGH", "title": "P", "description": "", "employee_refs": []},
        {"rule_id": "IE.PRSI.001", "severity": "HIGH", "title": "R", "description": "", "employee_refs": []},
    ]
    report = build_exposure_report(findings)
    names = [c.category for c in report.categories]
    assert names == sorted(names)
    assert names == ["IE.PAYE.001", "IE.PRSI.001", "IE.USC.001"]


def test_total_exposure_and_severity_counts():
    """IE-2026.01: report includes total_exposure and severity_counts."""
    findings = [
        {"rule_id": "IE.NET.001", "severity": "CRITICAL", "title": "T", "description": "", "amount_impact": 50.0, "employee_refs": ["E1"]},
        {"rule_id": "IE.PAY.001", "severity": "HIGH", "title": "T", "description": "", "amount_impact": None, "employee_refs": ["E2"]},
    ]
    report = build_exposure_report(findings)
    assert report.total_exposure == 50.0
    assert report.severity_counts.get("CRITICAL") == 1
    assert report.severity_counts.get("HIGH") == 1


def test_rule_breakdown():
    """IE-2026.01: report includes rule_breakdown with exposure_weight."""
    findings = [
        {"rule_id": "IE.NET.001", "severity": "CRITICAL", "title": "T", "description": "", "amount_impact": 10.0, "employee_refs": []},
        {"rule_id": "IE.NET.001", "severity": "CRITICAL", "title": "T", "description": "", "amount_impact": 20.0, "employee_refs": []},
    ]
    report = build_exposure_report(findings)
    assert len(report.rule_breakdown) >= 1
    net_rule = next((r for r in report.rule_breakdown if r.rule_id == "IE.NET.001"), None)
    assert net_rule is not None
    assert net_rule.finding_count == 2
    assert net_rule.total_amount_impact == 30.0
    assert net_rule.exposure_weight >= 1
