from core.scoring.risk import risk_points, compliance_score, score_bundle

def test_risk_points_weights():
    findings = [
        {"severity": "HIGH", "rule_id": "X"},
        {"severity": "LOW", "rule_id": "Y"},
        {"severity": "MEDIUM", "rule_id": "Z"},
    ]
    assert risk_points(findings) == 10 + 1 + 4

def test_compliance_score_bounds():
    assert compliance_score([]) == 100
    many_high = [{"severity": "HIGH", "rule_id": "X"}] * 100
    assert compliance_score(many_high) == 0

def test_score_bundle_shape():
    out = score_bundle([{"severity": "LOW", "rule_id": "IE.USC.001"}])
    assert "risk_points" in out
    assert "compliance_score" in out
    assert "counts_by_severity" in out
    assert "counts_by_rule" in out
