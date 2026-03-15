from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.normalize.schema import CanonicalPayrollRow

from core.rules.rules import (
    rule_sanity_001_gross_deduction_consistency,
    rule_sanity_004_deduction_breakdown_mismatch,
    rule_sanity_006_net_inconsistency,
    rule_sanity_007_net_upper_bound,
    rule_sanity_008_net_equals_gross_with_deductions,
    rule_sanity_009_deductions_exceed_gross,
    rule_payslip_001_missing_itemised,
    rule_payslip_002_gross_missing_or_zero,
    rule_gross_net_integrity,
    rule_sanity_002_negative_or_zero_gross,
    rule_sanity_003_impossible_or_negative_deductions,
    rule_sanity_005_negative_net,
    rule_paye_001_negative_or_impossible,
    rule_paye_003_zero_when_taxable_present,
    rule_paye_005_applied_when_taxable_zero,
    rule_paye_004_negative,
    rule_usc_004_negative,
    rule_prsi_003_negative,
    rule_negative_or_zero_pay,
    rule_usc_006_missing_above_threshold,
    rule_usc_deterministic_bounds,
    rule_prsi_004_applied_below_threshold,
    rule_prsi_005_missing_above_threshold,
    rule_prsi_deterministic_bounds,
    rule_net_deterministic_upper_bound,
    rule_paye_deterministic_bounds,
    rule_minimum_wage_deterministic,
    rule_auto_enrolment_deterministic,
    rule_usc_plausibility,
    rule_prsi_plausibility_class_a,
)

# ---------------------------------------------------------------------------
# Canonical execution order.
#
# Changing this tuple is a deliberate, reviewable action.  Any divergence
# between RULE_ORDER and the actual call sequence inside run_all() is caught
# by tests/test_rule_execution_order.py::test_rule_order_matches_run_all_source.
#
# Ordering contract:
#   1. Sanity / structural checks (HIGH severity, no config required)
#   2. Statutory bounds checks (HIGH severity, config-dependent)
#   3. Plausibility checks (LOW severity, config-dependent)
# ---------------------------------------------------------------------------
RULE_ORDER: tuple[str, ...] = (
    "rule_sanity_001_gross_deduction_consistency",
    "rule_sanity_004_deduction_breakdown_mismatch",
    "rule_sanity_006_net_inconsistency",
    "rule_sanity_007_net_upper_bound",
    "rule_sanity_008_net_equals_gross_with_deductions",
    "rule_sanity_009_deductions_exceed_gross",
    "rule_payslip_001_missing_itemised",
    "rule_payslip_002_gross_missing_or_zero",
    "rule_gross_net_integrity",
    "rule_sanity_002_negative_or_zero_gross",
    "rule_sanity_003_impossible_or_negative_deductions",
    "rule_sanity_005_negative_net",
    "rule_paye_001_negative_or_impossible",
    "rule_paye_003_zero_when_taxable_present",
    "rule_paye_005_applied_when_taxable_zero",
    "rule_paye_004_negative",
    "rule_usc_004_negative",
    "rule_prsi_003_negative",
    "rule_negative_or_zero_pay",
    "rule_usc_006_missing_above_threshold",
    "rule_usc_deterministic_bounds",
    "rule_prsi_004_applied_below_threshold",
    "rule_prsi_005_missing_above_threshold",
    "rule_prsi_deterministic_bounds",
    "rule_net_deterministic_upper_bound",
    "rule_paye_deterministic_bounds",
    "rule_minimum_wage_deterministic",
    "rule_auto_enrolment_deterministic",
    "rule_usc_plausibility",
    "rule_prsi_plausibility_class_a",
)

# Keys that every finding dict returned by run_all() must contain.
# Aligned with the Finding Pydantic schema in apps/api/schemas.py and
# the scoring layer in core/scoring/risk.py.
REQUIRED_FINDING_KEYS: frozenset[str] = frozenset({
    "rule_id",
    "severity",
    "title",
    "description",
    "evidence",
    "suggestion",
    "amount_impact",
    "employee_refs",
})

_CONFIG_PATH = Path(__file__).parent / "ie_config_2026.json"


def load_ie_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Load the Irish payroll compliance configuration from JSON.

    Defaults to the bundled ie_config_2026.json in this package directory.
    Pass an explicit path to override (useful in tests).
    """
    p = Path(path) if path is not None else _CONFIG_PATH
    with open(p, encoding="utf-8-sig") as fh:
        return json.load(fh)


def run_all(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    findings: List[dict] = []

    findings += rule_sanity_001_gross_deduction_consistency(rows)
    findings += rule_sanity_004_deduction_breakdown_mismatch(rows)
    findings += rule_sanity_006_net_inconsistency(rows)
    findings += rule_sanity_007_net_upper_bound(rows)
    findings += rule_sanity_008_net_equals_gross_with_deductions(rows)
    findings += rule_sanity_009_deductions_exceed_gross(rows)
    findings += rule_payslip_001_missing_itemised(rows)
    findings += rule_payslip_002_gross_missing_or_zero(rows)
    findings += rule_gross_net_integrity(rows)
    findings += rule_sanity_002_negative_or_zero_gross(rows)
    findings += rule_sanity_003_impossible_or_negative_deductions(rows)
    findings += rule_sanity_005_negative_net(rows)
    findings += rule_paye_001_negative_or_impossible(rows)
    findings += rule_paye_003_zero_when_taxable_present(rows, config)
    findings += rule_paye_005_applied_when_taxable_zero(rows)
    findings += rule_paye_004_negative(rows)
    findings += rule_usc_004_negative(rows)
    findings += rule_prsi_003_negative(rows)
    findings += rule_negative_or_zero_pay(rows)

    # Phase 2 deterministic bounds (HIGH)
    findings += rule_usc_006_missing_above_threshold(rows, config)
    findings += rule_usc_deterministic_bounds(rows, config)
    findings += rule_prsi_004_applied_below_threshold(rows, config)
    findings += rule_prsi_005_missing_above_threshold(rows, config)
    findings += rule_prsi_deterministic_bounds(rows, config)
    findings += rule_net_deterministic_upper_bound(rows, config)
    findings += rule_paye_deterministic_bounds(rows, config)
    findings += rule_minimum_wage_deterministic(rows, config)
    findings += rule_auto_enrolment_deterministic(rows, config)

    # Phase 1 plausibility (LOW)
    findings += rule_usc_plausibility(rows, config)
    findings += rule_prsi_plausibility_class_a(rows, config)

    return findings
