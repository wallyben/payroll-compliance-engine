"""
Regression guard: SANITY.006 duplicate finding removed from execution pipeline.

Background (ENGINE_AUDIT.md):
  SANITY.001 and SANITY.006 evaluated an identical condition:
    abs(net_pay - (gross_pay - known_deductions)) > 0.02
  Both were in RULE_ORDER and run_all(), so a single net-pay inconsistency
  produced two HIGH findings (+20 risk points instead of +10) and appeared
  twice in PDF output.

Fix: SANITY.006 removed from RULE_ORDER and run_all(); SANITY.001 is canonical.

Tests:
  1. Crafted dirty row with net-pay inconsistency → exactly ONE finding from run_all().
  2. That finding's rule_id == "IE.SANITY.001".
  3. risk_points() == 10 (one HIGH finding, not 20 from two HIGH findings).
  4. compliance_score() reflects single-finding penalty, not double.
  5. SANITY.006 is absent from RULE_ORDER entirely.
  6. run_all() source contains no call to rule_sanity_006_net_inconsistency.
  7. A clean row produces zero findings (no false positives from change).
  8. rule_sanity_006_net_inconsistency still callable in rules module (not deleted,
     just retired from the execution pipeline — safe for any direct callers).
  9. Calling rule_sanity_006 directly on the dirty row still returns a finding
     (function behaviour unchanged; it's just not wired into run_all).
 10. Direct call to SANITY.001 on dirty row returns exactly one finding.
 11. Risk points: two independent HIGH findings = 20 (scoring layer unchanged).
 12. risk_band() for score derived from single HIGH finding is correct.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict

import pytest

from core.normalize.schema import CanonicalPayrollRow
from core.rules.engine import RULE_ORDER, run_all
from core.rules.rules import (
    rule_sanity_001_gross_deduction_consistency,
    rule_sanity_006_net_inconsistency,
)
from core.scoring.risk import compliance_score, risk_band, risk_points

# ---------------------------------------------------------------------------
# Config fixture (minimal — only sections needed by sanity / scoring tests)
# ---------------------------------------------------------------------------

_CFG: Dict[str, Any] = {
    "usc": {
        "exemption_limit": 13000,
        "bands": [
            {"cap": 12012, "rate": 0.005},
            {"cap": 28700, "rate": 0.02},
            {"cap": 70044, "rate": 0.03},
            {"cap": None,  "rate": 0.08},
        ],
    },
    "income_tax": {
        "standard_rate_band_single": 44000,
        "standard_rate": 0.2,
        "higher_rate": 0.4,
    },
    "prsi": {
        "class_a": {
            "employee_rate_pre_2026_10_01": 0.042,
            "employer_rate_higher": 0.114,
            "employer_rate_lower": 0.0915,
            "weekly_threshold_for_higher": 552,
            "weekly_threshold_lower": 352,
        }
    },
    "minimum_wage": {"hourly_rate": 12.70},
    "auto_enrolment": {"eligibility": {"annual_earnings_min": 20000}},
}

# ---------------------------------------------------------------------------
# Row fixtures
# ---------------------------------------------------------------------------

# Dirty row: net_pay is inconsistent (too low relative to gross - deductions).
# Construction:
#   gross = 3000, paye = 600, usc = 51, prsi_ee = 126, pension_ee = 0
#   expected_net = 3000 - (600+51+126+0) = 2223
#   actual net_pay = 1900  →  |1900 - 2223| = 323 > 0.02  →  SANITY.001 fires
#
# Net is LOWER than expected so SANITY.007/NET.002 (upper-bound checks) do NOT
# fire, ensuring only the net-consistency rule produces a finding for this row.
# USC (51) is within plausibility band (~51.07 expected); PRSI (126) == 126 cap.
_DIRTY = CanonicalPayrollRow(
    employee_id="DIRTY_NET",
    gross_pay=3000.0,
    net_pay=1900.0,
    paye=600.0,
    usc=51.0,
    prsi_ee=126.0,
    prsi_er=0.0,
    pension_ee=0.0,
)

# Clean row: net = gross - (paye+usc+prsi_ee+pension_ee) exactly.
_CLEAN = CanonicalPayrollRow(
    employee_id="CLEAN",
    gross_pay=2000.0,
    net_pay=1691.0,
    paye=200.0,
    usc=25.0,
    prsi_ee=84.0,
    prsi_er=183.0,
    pension_ee=0.0,
)

# ---------------------------------------------------------------------------
# 1–4. Core regression: single finding, correct rule_id, correct scoring
# ---------------------------------------------------------------------------


def test_net_inconsistency_produces_exactly_one_finding():
    """A net-pay inconsistency must produce exactly one finding from run_all()."""
    findings = run_all([_DIRTY], _CFG)
    assert len(findings) == 1, (
        f"Expected 1 finding, got {len(findings)}: "
        f"{[f['rule_id'] for f in findings]}"
    )


def test_net_inconsistency_finding_is_sanity_001():
    """The single finding for net inconsistency must be IE.SANITY.001, not IE.SANITY.006."""
    findings = run_all([_DIRTY], _CFG)
    assert findings[0]["rule_id"] == "IE.SANITY.001"


def test_net_inconsistency_risk_points_is_10_not_20():
    """One HIGH finding = 10 risk points. Before the fix it was 20 (duplicate rule)."""
    findings = run_all([_DIRTY], _CFG)
    assert risk_points(findings) == 10


def test_net_inconsistency_compliance_score_reflects_single_penalty():
    """compliance_score with one HIGH finding must differ from a two-finding scenario."""
    single_finding = run_all([_DIRTY], _CFG)
    score_single = compliance_score(single_finding)
    # Two HIGH findings (pre-fix scenario) would give 20 risk points
    double_findings = single_finding + single_finding
    score_double = compliance_score(double_findings)
    assert score_single > score_double, (
        "Single-finding score must be higher than double-finding score."
    )
    # Concrete: 10 pts → 90, 20 pts → 80
    assert score_single == 90
    assert score_double == 80


# ---------------------------------------------------------------------------
# 5–6. SANITY.006 absent from RULE_ORDER and run_all() source
# ---------------------------------------------------------------------------


def test_sanity_006_not_in_rule_order():
    """SANITY.006 must not appear in RULE_ORDER."""
    assert "rule_sanity_006_net_inconsistency" not in RULE_ORDER, (
        "rule_sanity_006_net_inconsistency must be removed from RULE_ORDER."
    )


def test_sanity_006_not_called_in_run_all_source():
    """run_all() source must contain no call to rule_sanity_006_net_inconsistency."""
    src = inspect.getsource(run_all)
    assert "rule_sanity_006_net_inconsistency" not in src, (
        "run_all() still calls rule_sanity_006_net_inconsistency."
    )


def test_sanity_001_in_rule_order():
    """SANITY.001 must remain in RULE_ORDER as the canonical rule."""
    assert "rule_sanity_001_gross_deduction_consistency" in RULE_ORDER


def test_rule_order_has_no_duplicate_net_consistency_rules():
    """Only one net-consistency rule must appear in RULE_ORDER."""
    net_rules = [r for r in RULE_ORDER if "net_inconsistency" in r or "gross_deduction_consistency" in r]
    assert len(net_rules) == 1
    assert net_rules[0] == "rule_sanity_001_gross_deduction_consistency"


# ---------------------------------------------------------------------------
# 7. Clean row produces no findings (no regression from the removal)
# ---------------------------------------------------------------------------


def test_clean_row_produces_no_findings():
    """Removing SANITY.006 must not introduce false negatives on clean data."""
    assert run_all([_CLEAN], _CFG) == []


def test_clean_row_risk_points_zero():
    findings = run_all([_CLEAN], _CFG)
    assert risk_points(findings) == 0


# ---------------------------------------------------------------------------
# 8–9. rule_sanity_006 still callable; function behaviour unchanged
# ---------------------------------------------------------------------------


def test_sanity_006_function_still_callable():
    """rule_sanity_006_net_inconsistency must still exist in rules.py (not deleted)."""
    assert callable(rule_sanity_006_net_inconsistency)


def test_sanity_006_direct_call_on_dirty_row_returns_finding():
    """When called directly, SANITY.006 still detects the inconsistency (function unchanged)."""
    findings = rule_sanity_006_net_inconsistency([_DIRTY])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.006"
    assert findings[0]["severity"] == "HIGH"


def test_sanity_006_direct_call_on_clean_row_returns_empty():
    """When called directly, SANITY.006 returns no findings for a clean row."""
    assert rule_sanity_006_net_inconsistency([_CLEAN]) == []


# ---------------------------------------------------------------------------
# 10. Direct call to SANITY.001 on dirty row is the single canonical finding
# ---------------------------------------------------------------------------


def test_sanity_001_direct_call_on_dirty_row_returns_one_finding():
    findings = rule_sanity_001_gross_deduction_consistency([_DIRTY])
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "IE.SANITY.001"
    assert findings[0]["severity"] == "HIGH"


def test_sanity_001_direct_call_on_clean_row_returns_empty():
    assert rule_sanity_001_gross_deduction_consistency([_CLEAN]) == []


# ---------------------------------------------------------------------------
# 11. Scoring layer unchanged: two independent HIGH findings still = 20 pts
# ---------------------------------------------------------------------------


def test_two_high_findings_score_20_points():
    """The scoring layer itself is unchanged; two HIGH findings = 20 pts."""
    two_findings = [
        {"rule_id": "IE.SANITY.001", "severity": "HIGH",
         "title": "", "description": "", "evidence": {}, "suggestion": "",
         "amount_impact": None, "employee_refs": []},
        {"rule_id": "IE.PRSI.002", "severity": "HIGH",
         "title": "", "description": "", "evidence": {}, "suggestion": "",
         "amount_impact": None, "employee_refs": []},
    ]
    assert risk_points(two_findings) == 20


# ---------------------------------------------------------------------------
# 12. risk_band for single HIGH finding
# ---------------------------------------------------------------------------


def test_risk_band_for_single_high_finding():
    """90-point score (one HIGH finding) is in LOW_RISK band."""
    assert risk_band(90) == "LOW_RISK"


def test_risk_band_for_double_high_finding_pre_fix_scenario():
    """80-point score (two HIGH findings, pre-fix) crosses into MEDIUM_RISK.

    This demonstrates the real-world impact of the duplicate: one net-pay
    inconsistency was enough to push a run from LOW_RISK (score 90) to
    MEDIUM_RISK (score 80), triggering escalation workflows incorrectly.
    """
    assert risk_band(80) == "MEDIUM_RISK"
