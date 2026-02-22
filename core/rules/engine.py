from __future__ import annotations
from typing import List, Dict, Any
from core.normalize.schema import CanonicalPayrollRow

from core.rules.rules import (
    rule_sanity_001_gross_deduction_consistency,
    rule_sanity_004_deduction_breakdown_mismatch,
    rule_gross_net_integrity,
    rule_sanity_002_negative_or_zero_gross,
    rule_sanity_003_impossible_or_negative_deductions,
    rule_sanity_005_negative_net,
    rule_paye_001_negative_or_impossible,
    rule_paye_003_zero_when_taxable_present,
    rule_paye_005_applied_when_taxable_zero,
    rule_paye_004_negative,
    rule_usc_004_negative,
    rule_usc_006_missing_above_threshold,
    rule_prsi_003_negative,
    rule_prsi_004_applied_below_threshold,
    rule_prsi_005_missing_above_threshold,
    rule_negative_or_zero_pay,
    rule_usc_deterministic_bounds,
    rule_prsi_deterministic_bounds,
    rule_net_deterministic_upper_bound,
    rule_paye_deterministic_bounds,
    rule_minimum_wage_deterministic,
    rule_auto_enrolment_deterministic,
    rule_usc_plausibility,
    rule_prsi_plausibility_class_a,
)


def run_all(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    findings: List[dict] = []

    findings += rule_sanity_001_gross_deduction_consistency(rows)
    findings += rule_sanity_004_deduction_breakdown_mismatch(rows)
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
