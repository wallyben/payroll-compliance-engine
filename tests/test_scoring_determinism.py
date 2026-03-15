"""
Phase 4: scoring hardening — determinism and contract tests.

Covers:
- SEVERITY_WEIGHTS constant values are frozen and correct.
- SEVERITY_WEIGHTS is immutable (MappingProxyType — mutation raises TypeError).
- DEFAULT_SEVERITY_WEIGHTS is in sync with SEVERITY_WEIGHTS.
- KNOWN_SEVERITIES contains exactly the three expected severity labels.
- SCORE_MAX_POINTS is 100.
- RISK_BAND_THRESHOLDS is present and immutable.
- risk_points() is deterministic, weight-stable, and handles edge cases.
- compliance_score() stays in [0, 100], is deterministic, and degrades correctly.
- risk_band() maps score ranges to the correct labels.
- exposure_total in score_bundle() sums amount_impact values correctly.
- score_bundle() shape is stable and all keys are present.
- Empty / clean scenarios produce the expected output.
- Repeated runs produce identical results.
"""

from __future__ import annotations

import types
import pytest

from core.scoring.risk import (
    KNOWN_SEVERITIES,
    RISK_BAND_THRESHOLDS,
    SCORE_MAX_POINTS,
    SEVERITY_WEIGHTS,
    DEFAULT_SEVERITY_WEIGHTS,
    compliance_score,
    risk_band,
    risk_points,
    score_bundle,
    summarize_findings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(severity: str, rule_id: str = "IE.TEST.001", amount_impact=None) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": "",
        "description": "",
        "evidence": {},
        "suggestion": "",
        "amount_impact": amount_impact,
        "employee_refs": [],
    }


HIGH = _finding("HIGH")
MEDIUM = _finding("MEDIUM")
LOW = _finding("LOW")

# ---------------------------------------------------------------------------
# Constant contracts
# ---------------------------------------------------------------------------


def test_severity_weights_values():
    assert dict(SEVERITY_WEIGHTS) == {"HIGH": 10, "MEDIUM": 4, "LOW": 1}


def test_severity_weights_is_mapping_proxy():
    assert isinstance(SEVERITY_WEIGHTS, types.MappingProxyType)


def test_severity_weights_is_immutable():
    with pytest.raises(TypeError):
        SEVERITY_WEIGHTS["HIGH"] = 999  # type: ignore[index]


def test_severity_weights_high_greater_than_medium():
    assert SEVERITY_WEIGHTS["HIGH"] > SEVERITY_WEIGHTS["MEDIUM"]


def test_severity_weights_medium_greater_than_low():
    assert SEVERITY_WEIGHTS["MEDIUM"] > SEVERITY_WEIGHTS["LOW"]


def test_default_severity_weights_matches_severity_weights():
    """DEFAULT_SEVERITY_WEIGHTS must stay in sync with the frozen SEVERITY_WEIGHTS."""
    assert DEFAULT_SEVERITY_WEIGHTS == dict(SEVERITY_WEIGHTS)


def test_known_severities_values():
    assert KNOWN_SEVERITIES == frozenset({"HIGH", "MEDIUM", "LOW"})


def test_known_severities_is_frozenset():
    assert isinstance(KNOWN_SEVERITIES, frozenset)


def test_score_max_points_is_100():
    assert SCORE_MAX_POINTS == 100


def test_risk_band_thresholds_is_mapping_proxy():
    assert isinstance(RISK_BAND_THRESHOLDS, types.MappingProxyType)


def test_risk_band_thresholds_is_immutable():
    with pytest.raises(TypeError):
        RISK_BAND_THRESHOLDS[81] = "CHANGED"  # type: ignore[index]


def test_risk_band_thresholds_contains_four_bands():
    assert len(RISK_BAND_THRESHOLDS) == 4


def test_risk_band_thresholds_zero_is_lowest():
    """0 must be a threshold — ensures every valid score has a band."""
    assert 0 in RISK_BAND_THRESHOLDS


# ---------------------------------------------------------------------------
# risk_points()
# ---------------------------------------------------------------------------


def test_risk_points_empty():
    assert risk_points([]) == 0


def test_risk_points_single_high():
    assert risk_points([HIGH]) == 10


def test_risk_points_single_medium():
    assert risk_points([MEDIUM]) == 4


def test_risk_points_single_low():
    assert risk_points([LOW]) == 1


def test_risk_points_mixed():
    assert risk_points([HIGH, MEDIUM, LOW]) == 15


def test_risk_points_multiple_highs():
    assert risk_points([HIGH, HIGH, HIGH]) == 30


def test_risk_points_unknown_severity_contributes_zero():
    unknown = _finding("CRITICAL")
    assert risk_points([unknown]) == 0


def test_risk_points_none_severity_contributes_zero():
    null_sev = {"rule_id": "X", "severity": None}
    assert risk_points([null_sev]) == 0


def test_risk_points_missing_severity_contributes_zero():
    no_sev = {"rule_id": "X"}
    assert risk_points([no_sev]) == 0


def test_risk_points_is_integer():
    assert isinstance(risk_points([HIGH, LOW]), int)


def test_risk_points_is_deterministic():
    findings = [HIGH, MEDIUM, LOW, HIGH]
    assert risk_points(findings) == risk_points(findings)


def test_risk_points_custom_weights():
    custom = {"HIGH": 5, "MEDIUM": 2, "LOW": 0}
    assert risk_points([HIGH, MEDIUM, LOW], weights=custom) == 7


def test_risk_points_custom_weights_do_not_mutate_defaults():
    custom = {"HIGH": 999}
    risk_points([HIGH], weights=custom)
    assert DEFAULT_SEVERITY_WEIGHTS["HIGH"] == 10
    assert SEVERITY_WEIGHTS["HIGH"] == 10


def test_risk_points_order_independent():
    """Score must be the same regardless of finding list order."""
    assert risk_points([HIGH, MEDIUM, LOW]) == risk_points([LOW, HIGH, MEDIUM])


# ---------------------------------------------------------------------------
# compliance_score()
# ---------------------------------------------------------------------------


def test_compliance_score_empty_is_100():
    assert compliance_score([]) == 100


def test_compliance_score_100_high_findings_is_0():
    assert compliance_score([HIGH] * 100) == 0


def test_compliance_score_is_in_0_100_range():
    for n in range(0, 25):
        score = compliance_score([HIGH] * n)
        assert 0 <= score <= 100, f"Score out of range for {n} HIGH findings: {score}"


def test_compliance_score_never_below_0():
    assert compliance_score([HIGH] * 1000) == 0


def test_compliance_score_never_above_100():
    assert compliance_score([]) == 100
    assert compliance_score([LOW]) <= 100


def test_compliance_score_is_integer():
    assert isinstance(compliance_score([HIGH, LOW]), int)


def test_compliance_score_decreases_with_more_violations():
    assert compliance_score([HIGH]) < compliance_score([])
    assert compliance_score([HIGH, HIGH]) < compliance_score([HIGH])


def test_compliance_score_is_deterministic():
    findings = [HIGH, MEDIUM, LOW]
    assert compliance_score(findings) == compliance_score(findings)


def test_compliance_score_same_points_same_score():
    # One HIGH (10pts) vs ten LOWs (10pts) → same score
    assert compliance_score([HIGH]) == compliance_score([LOW] * 10)


def test_compliance_score_respects_custom_max_points():
    # With max_points=10, one HIGH (10pts) → score 0
    assert compliance_score([HIGH], max_points=10) == 0


# ---------------------------------------------------------------------------
# risk_band()
# ---------------------------------------------------------------------------


def test_risk_band_100_is_low_risk():
    assert risk_band(100) == "LOW_RISK"


def test_risk_band_81_is_low_risk():
    assert risk_band(81) == "LOW_RISK"


def test_risk_band_80_is_medium_risk():
    assert risk_band(80) == "MEDIUM_RISK"


def test_risk_band_51_is_medium_risk():
    assert risk_band(51) == "MEDIUM_RISK"


def test_risk_band_50_is_high_risk():
    assert risk_band(50) == "HIGH_RISK"


def test_risk_band_21_is_high_risk():
    assert risk_band(21) == "HIGH_RISK"


def test_risk_band_20_is_critical():
    assert risk_band(20) == "CRITICAL"


def test_risk_band_0_is_critical():
    assert risk_band(0) == "CRITICAL"


def test_risk_band_returns_string():
    for s in range(0, 101, 10):
        assert isinstance(risk_band(s), str)


def test_risk_band_is_deterministic():
    for s in (0, 20, 50, 80, 100):
        assert risk_band(s) == risk_band(s)


def test_risk_band_thresholds_cover_full_0_100_range():
    """Every integer score in [0, 100] must resolve to a known band."""
    known_bands = set(RISK_BAND_THRESHOLDS.values())
    for s in range(0, 101):
        b = risk_band(s)
        assert b in known_bands, f"Score {s} returned unknown band '{b}'"


# ---------------------------------------------------------------------------
# score_bundle() — shape and key contract
# ---------------------------------------------------------------------------

_REQUIRED_BUNDLE_KEYS = {
    "risk_points",
    "compliance_score",
    "risk_band",
    "exposure_total",
    "counts_by_severity",
    "counts_by_rule",
    "total_findings",
}


def test_score_bundle_has_all_required_keys():
    bundle = score_bundle([HIGH])
    missing = _REQUIRED_BUNDLE_KEYS - set(bundle.keys())
    assert missing == set(), f"score_bundle missing keys: {missing}"


def test_score_bundle_risk_points_matches_risk_points_function():
    findings = [HIGH, MEDIUM, LOW]
    assert score_bundle(findings)["risk_points"] == risk_points(findings)


def test_score_bundle_compliance_score_matches_compliance_score_function():
    findings = [HIGH, MEDIUM]
    assert score_bundle(findings)["compliance_score"] == compliance_score(findings)


def test_score_bundle_risk_band_matches_risk_band_function():
    findings = [HIGH]
    bundle = score_bundle(findings)
    assert bundle["risk_band"] == risk_band(bundle["compliance_score"])


def test_score_bundle_total_findings_matches_input_length():
    findings = [HIGH, LOW, MEDIUM]
    assert score_bundle(findings)["total_findings"] == 3


def test_score_bundle_counts_by_severity_correct():
    findings = [HIGH, HIGH, MEDIUM, LOW]
    counts = score_bundle(findings)["counts_by_severity"]
    assert counts["HIGH"] == 2
    assert counts["MEDIUM"] == 1
    assert counts["LOW"] == 1


def test_score_bundle_counts_by_rule_groups_correctly():
    findings = [
        _finding("HIGH", rule_id="IE.PAYE.001"),
        _finding("HIGH", rule_id="IE.PAYE.001"),
        _finding("LOW",  rule_id="IE.USC.001"),
    ]
    by_rule = score_bundle(findings)["counts_by_rule"]
    assert by_rule["IE.PAYE.001"] == 2
    assert by_rule["IE.USC.001"] == 1


# ---------------------------------------------------------------------------
# score_bundle() — exposure_total
# ---------------------------------------------------------------------------


def test_exposure_total_empty_findings_is_zero():
    assert score_bundle([])["exposure_total"] == 0.0


def test_exposure_total_sums_amount_impact_values():
    findings = [
        _finding("HIGH", amount_impact=100.0),
        _finding("HIGH", amount_impact=250.50),
        _finding("LOW",  amount_impact=49.50),
    ]
    assert score_bundle(findings)["exposure_total"] == 400.0


def test_exposure_total_excludes_none_impact():
    findings = [
        _finding("HIGH", amount_impact=200.0),
        _finding("HIGH", amount_impact=None),
        _finding("LOW",  amount_impact=50.0),
    ]
    assert score_bundle(findings)["exposure_total"] == 250.0


def test_exposure_total_all_none_impact_is_zero():
    findings = [_finding("HIGH", amount_impact=None) for _ in range(5)]
    assert score_bundle(findings)["exposure_total"] == 0.0


def test_exposure_total_rounds_to_two_decimal_places():
    findings = [
        _finding("HIGH", amount_impact=0.001),
        _finding("HIGH", amount_impact=0.004),
    ]
    result = score_bundle(findings)["exposure_total"]
    # 0.001 + 0.004 = 0.005, rounded to 2dp → 0.01
    assert result == round(0.001 + 0.004, 2)


def test_exposure_total_is_float():
    bundle = score_bundle([_finding("HIGH", amount_impact=100.0)])
    assert isinstance(bundle["exposure_total"], float)


def test_exposure_total_is_deterministic():
    findings = [_finding("HIGH", amount_impact=99.99), _finding("LOW", amount_impact=0.01)]
    assert score_bundle(findings)["exposure_total"] == score_bundle(findings)["exposure_total"]


# ---------------------------------------------------------------------------
# score_bundle() — empty / clean scenarios
# ---------------------------------------------------------------------------


def test_score_bundle_empty_findings():
    bundle = score_bundle([])
    assert bundle["risk_points"] == 0
    assert bundle["compliance_score"] == 100
    assert bundle["risk_band"] == "LOW_RISK"
    assert bundle["exposure_total"] == 0.0
    assert bundle["total_findings"] == 0
    assert bundle["counts_by_severity"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    assert bundle["counts_by_rule"] == {}


def test_score_bundle_clean_run_is_full_score():
    bundle = score_bundle([])
    assert bundle["compliance_score"] == 100
    assert bundle["risk_band"] == "LOW_RISK"


# ---------------------------------------------------------------------------
# Determinism: repeated calls produce identical output
# ---------------------------------------------------------------------------


def test_score_bundle_is_deterministic_empty():
    assert score_bundle([]) == score_bundle([])


def test_score_bundle_is_deterministic_single_finding():
    assert score_bundle([HIGH]) == score_bundle([HIGH])


def test_score_bundle_is_deterministic_mixed_findings():
    findings = [HIGH, HIGH, MEDIUM, LOW, _finding("HIGH", amount_impact=500.0)]
    assert score_bundle(findings) == score_bundle(findings)


def test_score_bundle_is_deterministic_across_three_calls():
    findings = [HIGH, MEDIUM, LOW]
    b1 = score_bundle(findings)
    b2 = score_bundle(findings)
    b3 = score_bundle(findings)
    assert b1 == b2 == b3


def test_risk_points_deterministic_across_three_calls():
    findings = [HIGH, MEDIUM, LOW]
    assert risk_points(findings) == risk_points(findings) == risk_points(findings)


def test_compliance_score_deterministic_across_three_calls():
    findings = [HIGH, MEDIUM, LOW]
    s1 = compliance_score(findings)
    s2 = compliance_score(findings)
    s3 = compliance_score(findings)
    assert s1 == s2 == s3


# ---------------------------------------------------------------------------
# summarize_findings()
# ---------------------------------------------------------------------------


def test_summarize_findings_empty():
    result = summarize_findings([])
    assert result["total_findings"] == 0
    assert result["counts_by_severity"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    assert result["counts_by_rule"] == {}


def test_summarize_findings_counts_severities():
    result = summarize_findings([HIGH, HIGH, MEDIUM])
    assert result["counts_by_severity"]["HIGH"] == 2
    assert result["counts_by_severity"]["MEDIUM"] == 1
    assert result["counts_by_severity"]["LOW"] == 0


def test_summarize_findings_ignores_unknown_severity():
    result = summarize_findings([_finding("UNKNOWN_SEV")])
    assert result["total_findings"] == 1
    assert result["counts_by_severity"]["HIGH"] == 0


def test_summarize_findings_total_matches_input_length():
    findings = [HIGH, MEDIUM, LOW, HIGH]
    assert summarize_findings(findings)["total_findings"] == 4
