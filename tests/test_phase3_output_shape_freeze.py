from apps.api.schemas import RunOut, Finding

def test_phase3_runout_output_shape_freeze():

    findings = [
        {
            "rule_id": "IE.TEST.001",
            "severity": "HIGH",
            "title": "Test",
            "description": "Desc",
            "evidence": {},
            "suggestion": "",
            "amount_impact": None,
            "employee_refs": []
        }
    ]

    run = RunOut(
        id=1,
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings=[Finding(**f) for f in findings],
        counts={"total": 1, "valid": 1, "invalid": 0},
        invalid_rows=[],
        risk_points=5,
        compliance_score=95.0,
        severity_summary={"HIGH":1,"MEDIUM":0,"LOW":0,"TOTAL":1}
    )

    expected_keys = {
        "id",
        "upload_id",
        "mapping_id",
        "ruleset_version",
        "findings",
        "counts",
        "invalid_rows",
        "risk_points",
        "compliance_score",
        "severity_summary",
    }

    assert set(run.model_dump().keys()) == expected_keys
