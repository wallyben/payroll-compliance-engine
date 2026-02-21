from apps.api.schemas import RunOut, Finding
from core.scoring.risk import score_bundle

def test_phase3_runout_exposes_score_fields():

    findings = [
        {
            "rule_id": "IE.TEST.001",
            "severity": "HIGH",
            "title": "Test",
            "description": "Test desc",
            "evidence": {},
            "suggestion": "",
            "amount_impact": None,
            "employee_refs": []
        }
    ]

    bundle = score_bundle(findings)

    run = RunOut(
        id=1,
        upload_id=1,
        mapping_id=1,
        ruleset_version="IE-2026.01",
        findings=[Finding(**f) for f in findings],
        counts={"total": 1, "valid": 1, "invalid": 0},
        invalid_rows=[],
        risk_points=bundle["risk_points"],
        compliance_score=bundle["compliance_score"],
    )

    assert run.risk_points == bundle["risk_points"]
    assert run.compliance_score == bundle["compliance_score"]
