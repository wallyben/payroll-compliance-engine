from apps.api.schemas import RunOut, Finding

def test_phase3_severity_summary_counts():

    findings = [
        {"rule_id": "1", "severity": "HIGH", "title": "", "description": "", "evidence": {}, "suggestion": "", "amount_impact": None, "employee_refs": []},
        {"rule_id": "2", "severity": "MEDIUM", "title": "", "description": "", "evidence": {}, "suggestion": "", "amount_impact": None, "employee_refs": []},
        {"rule_id": "3", "severity": "LOW", "title": "", "description": "", "evidence": {}, "suggestion": "", "amount_impact": None, "employee_refs": []},
        {"rule_id": "4", "severity": "HIGH", "title": "", "description": "", "evidence": {}, "suggestion": "", "amount_impact": None, "employee_refs": []},
    ]

    summary = {
        "HIGH": 2,
        "MEDIUM": 1,
        "LOW": 1,
        "TOTAL": 4,
    }

    run = RunOut(
        id=1,
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings=[Finding(**f) for f in findings],
        counts={"total": 4, "valid": 4, "invalid": 0},
        invalid_rows=[],
        risk_points=10,
        compliance_score=75.0,
        severity_summary=summary
    )

    assert run.severity_summary == summary
