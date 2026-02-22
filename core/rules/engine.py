from __future__ import annotations
from typing import List, Dict, Any
from core.normalize.schema import CanonicalPayrollRow

from core.rules.rules import (
    rule_gross_net_integrity,
    rule_sanity_002_negative_or_zero_gross,
    rule_sanity_003_impossible_or_negative_deductions,
    rule_sanity_005_negative_net,
    rule_paye_004_negative,
    rule_usc_004_negative,
    rule_prsi_003_negative,
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

    findings += rule_gross_net_integrity(rows)
    findings += rule_sanity_002_negative_or_zero_gross(rows)
    findings += rule_sanity_003_impossible_or_negative_deductions(rows)
    findings += rule_sanity_005_negative_net(rows)
    findings += rule_paye_004_negative(rows)
    findings += rule_usc_004_negative(rows)
    findings += rule_prsi_003_negative(rows)
    findings += rule_negative_or_zero_pay(rows)

    # Phase 2 deterministic bounds (HIGH)
    findings += rule_usc_deterministic_bounds(rows, config)
    findings += rule_prsi_deterministic_bounds(rows, config)
    findings += rule_net_deterministic_upper_bound(rows, config)
    findings += rule_paye_deterministic_bounds(rows, config)
    findings += rule_minimum_wage_deterministic(rows, config)
    findings += rule_auto_enrolment_deterministic(rows, config)

    # Phase 1 plausibility (LOW)
    findings += rule_usc_plausibility(rows, config)
    findings += rule_prsi_plausibility_class_a(rows, config)

    return findings
