"""
tests/test_exposure_engine.py
------------------------------
Deterministic unit tests for core/reporting/exposure_engine.py.

Test cases:
  1. Clean findings list (no violations)     → exposure_total = 0
  2. Single rule violation                   → correct exposure returned
  3. Multiple violations                     → aggregated correctly
  4. Multiple employees impacted             → counted correctly (unique)
  5. Same input twice                        → identical output (determinism)
"""

import pytest

from core.reporting.exposure_engine import quantify_exposure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(rule_id: str, amount_impact=None, employee_refs=None) -> dict:
    """Build a minimal finding dict matching the repo's real structure."""
    return {
        "rule_id": rule_id,
        "severity": "HIGH",
        "title": "Test Finding",
        "description": "Test description",
        "evidence": {},
        "suggestion": "",
        "amount_impact": amount_impact,
        "employee_refs": employee_refs or [],
    }


# ---------------------------------------------------------------------------
# 1. Clean findings list → exposure_total = 0
# ---------------------------------------------------------------------------

class TestCleanFindings:
    def test_empty_list_returns_zero_exposure(self):
        result = quantify_exposure([])
        assert result["exposure_total"] == 0
        assert result["employees_impacted"] == 0
        assert result["exposure_by_rule"] == {}

    def test_findings_with_no_amount_impact_returns_zero(self):
        findings = [
            _finding("IE.PAYE.003", amount_impact=None, employee_refs=["E101"]),
            _finding("IE.USC.006", amount_impact=None, employee_refs=["E102"]),
        ]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 0
        assert result["exposure_by_rule"]["IE.PAYE.003"] == 0.0
        assert result["exposure_by_rule"]["IE.USC.006"] == 0.0


# ---------------------------------------------------------------------------
# 2. Single rule violation → correct exposure
# ---------------------------------------------------------------------------

class TestSingleViolation:
    def test_single_finding_exposure_returned(self):
        findings = [_finding("IE.MINWAGE.001", amount_impact=320.0, employee_refs=["E101"])]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 320.0
        assert result["employees_impacted"] == 1
        assert result["exposure_by_rule"] == {"IE.MINWAGE.001": 320.0}

    def test_fractional_amount_impact(self):
        findings = [_finding("IE.PAYE.003", amount_impact=99.99, employee_refs=["E201"])]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 99.99

    def test_zero_amount_impact(self):
        findings = [_finding("IE.PAYE.003", amount_impact=0.0, employee_refs=["E301"])]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 0.0
        assert result["employees_impacted"] == 1


# ---------------------------------------------------------------------------
# 3. Multiple violations → aggregated correctly
# ---------------------------------------------------------------------------

class TestMultipleViolations:
    def test_same_rule_multiple_findings_summed(self):
        """IE.MINWAGE.001 across 3 employees: 320 + 480 + 1120 = 1920."""
        findings = [
            _finding("IE.MINWAGE.001", amount_impact=320.0, employee_refs=["E101"]),
            _finding("IE.MINWAGE.001", amount_impact=480.0, employee_refs=["E102"]),
            _finding("IE.MINWAGE.001", amount_impact=1120.0, employee_refs=["E103"]),
        ]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 1920.0
        assert result["exposure_by_rule"] == {"IE.MINWAGE.001": 1920.0}

    def test_multiple_rules_aggregated_separately(self):
        findings = [
            _finding("IE.PAYE.003", amount_impact=500.0, employee_refs=["E201"]),
            _finding("IE.MINWAGE.001", amount_impact=320.0, employee_refs=["E202"]),
            _finding("IE.USC.006", amount_impact=150.0, employee_refs=["E203"]),
        ]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 970.0
        assert result["exposure_by_rule"]["IE.PAYE.003"] == 500.0
        assert result["exposure_by_rule"]["IE.MINWAGE.001"] == 320.0
        assert result["exposure_by_rule"]["IE.USC.006"] == 150.0

    def test_mixed_none_and_numeric_amounts(self):
        """None values contribute 0; numeric values are summed correctly."""
        findings = [
            _finding("IE.PAYE.003", amount_impact=200.0, employee_refs=["E101"]),
            _finding("IE.PAYE.003", amount_impact=None, employee_refs=["E102"]),
            _finding("IE.PAYE.003", amount_impact=300.0, employee_refs=["E103"]),
        ]
        result = quantify_exposure(findings)
        assert result["exposure_total"] == 500.0
        assert result["exposure_by_rule"]["IE.PAYE.003"] == 500.0

    def test_global_exposure_total_is_sum_of_all_rules(self):
        findings = [
            _finding("RULE.A", amount_impact=100.0, employee_refs=["E1"]),
            _finding("RULE.B", amount_impact=200.0, employee_refs=["E2"]),
            _finding("RULE.C", amount_impact=300.0, employee_refs=["E3"]),
        ]
        result = quantify_exposure(findings)
        expected_total = (
            result["exposure_by_rule"]["RULE.A"]
            + result["exposure_by_rule"]["RULE.B"]
            + result["exposure_by_rule"]["RULE.C"]
        )
        assert result["exposure_total"] == expected_total


# ---------------------------------------------------------------------------
# 4. Multiple employees impacted → counted correctly
# ---------------------------------------------------------------------------

class TestEmployeeImpact:
    def test_three_distinct_employees_counted(self):
        findings = [
            _finding("IE.PAYE.003", amount_impact=100.0, employee_refs=["E101"]),
            _finding("IE.PAYE.003", amount_impact=200.0, employee_refs=["E102"]),
            _finding("IE.PAYE.003", amount_impact=300.0, employee_refs=["E103"]),
        ]
        result = quantify_exposure(findings)
        assert result["employees_impacted"] == 3

    def test_same_employee_across_multiple_findings_counted_once(self):
        """E101 appears in two different rule findings – should count once."""
        findings = [
            _finding("IE.PAYE.003", amount_impact=100.0, employee_refs=["E101"]),
            _finding("IE.MINWAGE.001", amount_impact=200.0, employee_refs=["E101"]),
        ]
        result = quantify_exposure(findings)
        assert result["employees_impacted"] == 1

    def test_multi_employee_refs_in_single_finding(self):
        """A single finding referencing multiple employees counts each once."""
        findings = [
            _finding("IE.PAYE.003", amount_impact=300.0, employee_refs=["E101", "E102", "E103"]),
        ]
        result = quantify_exposure(findings)
        assert result["employees_impacted"] == 3

    def test_no_employee_refs_gives_zero_impacted(self):
        findings = [_finding("IE.PAYE.003", amount_impact=500.0, employee_refs=[])]
        result = quantify_exposure(findings)
        assert result["employees_impacted"] == 0

    def test_missing_employee_refs_key_treated_as_empty(self):
        finding = {
            "rule_id": "IE.PAYE.003",
            "severity": "HIGH",
            "title": "Test",
            "description": "Test",
            "amount_impact": 100.0,
            # no employee_refs key
        }
        result = quantify_exposure([finding])
        assert result["employees_impacted"] == 0
        assert result["exposure_total"] == 100.0


# ---------------------------------------------------------------------------
# 5. Same input twice → identical output (determinism)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_produces_same_output(self):
        findings = [
            _finding("IE.PAYE.003", amount_impact=500.0, employee_refs=["E201"]),
            _finding("IE.MINWAGE.001", amount_impact=320.0, employee_refs=["E202"]),
            _finding("IE.USC.006", amount_impact=150.0, employee_refs=["E203"]),
        ]
        result1 = quantify_exposure(findings)
        result2 = quantify_exposure(findings)
        assert result1 == result2

    def test_same_input_same_key_ordering(self):
        """exposure_by_rule keys must be in the same order across runs."""
        findings = [
            _finding("IE.PAYE.003", amount_impact=500.0, employee_refs=["E201"]),
            _finding("IE.MINWAGE.001", amount_impact=320.0, employee_refs=["E202"]),
            _finding("IE.USC.006", amount_impact=150.0, employee_refs=["E203"]),
        ]
        result1 = quantify_exposure(findings)
        result2 = quantify_exposure(findings)
        assert list(result1["exposure_by_rule"].keys()) == list(result2["exposure_by_rule"].keys())

    def test_numeric_stability_across_runs(self):
        """exposure_total must be bit-for-bit identical across repeated calls."""
        findings = [
            _finding("IE.MINWAGE.001", amount_impact=320.0, employee_refs=["E101"]),
            _finding("IE.MINWAGE.001", amount_impact=480.0, employee_refs=["E102"]),
            _finding("IE.MINWAGE.001", amount_impact=1120.0, employee_refs=["E103"]),
        ]
        totals = {quantify_exposure(findings)["exposure_total"] for _ in range(5)}
        assert len(totals) == 1, "exposure_total must not vary across runs"

    def test_input_list_is_not_mutated(self):
        """The function must not mutate the input findings list."""
        findings = [
            _finding("IE.PAYE.003", amount_impact=100.0, employee_refs=["E101"]),
        ]
        original = [dict(f) for f in findings]
        quantify_exposure(findings)
        assert findings[0] == original[0]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_amount_impact_key(self):
        finding = {
            "rule_id": "IE.PRSI.005",
            "severity": "HIGH",
            "title": "Test",
            "description": "Test",
            "employee_refs": ["E501"],
        }
        result = quantify_exposure([finding])
        assert result["exposure_total"] == 0.0

    def test_missing_rule_id_key_falls_back_to_unknown(self):
        finding = {
            "severity": "HIGH",
            "amount_impact": 99.0,
            "employee_refs": ["E601"],
        }
        result = quantify_exposure([finding])
        assert result["exposure_total"] == 99.0
        assert "UNKNOWN" in result["exposure_by_rule"]

    def test_exposure_by_rule_keys_sorted_lexicographically(self):
        findings = [
            _finding("RULE.Z", amount_impact=1.0),
            _finding("RULE.A", amount_impact=2.0),
            _finding("RULE.M", amount_impact=3.0),
        ]
        result = quantify_exposure(findings)
        keys = list(result["exposure_by_rule"].keys())
        assert keys == sorted(keys)
