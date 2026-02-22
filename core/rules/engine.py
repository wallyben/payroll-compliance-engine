from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any, Callable, Tuple
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

# core/rules/engine.py -> parent.parent.parent = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SCAN_PROFILES_DIR = _PROJECT_ROOT / "config" / "scan_profiles"


def _load_scan_profile(profile_name: str) -> Dict[str, Any]:
    path = _SCAN_PROFILES_DIR / f"{profile_name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _run_with_profile(
    rows: List[CanonicalPayrollRow],
    config: Dict[str, Any],
    active_rules: set,
    rule_list: List[Tuple[List[str], Callable]],
) -> List[dict]:
    findings: List[dict] = []
    for rule_ids, runner in rule_list:
        if not any(rid in active_rules for rid in rule_ids):
            continue
        result = runner(rows, config)
        for f in result:
            if f.get("rule_id") in active_rules:
                findings.append(f)
    return findings


def run_all(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    profile_name = config.get("scan_profile")
    if profile_name:
        profile = _load_scan_profile(profile_name)
        active_rules = set(profile.get("active_rules", []))
        return _run_with_profile(rows, config, active_rules, _RULE_LIST)

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
    findings += rule_usc_006_missing_above_threshold(rows, config)
    findings += rule_usc_deterministic_bounds(rows, config)
    findings += rule_prsi_004_applied_below_threshold(rows, config)
    findings += rule_prsi_005_missing_above_threshold(rows, config)
    findings += rule_prsi_deterministic_bounds(rows, config)
    findings += rule_net_deterministic_upper_bound(rows, config)
    findings += rule_paye_deterministic_bounds(rows, config)
    findings += rule_minimum_wage_deterministic(rows, config)
    findings += rule_auto_enrolment_deterministic(rows, config)
    findings += rule_usc_plausibility(rows, config)
    findings += rule_prsi_plausibility_class_a(rows, config)
    return findings


def _runner(rows: List[CanonicalPayrollRow], config: Dict[str, Any], fn: Callable, takes_config: bool = False):
    if takes_config:
        return fn(rows, config)
    return fn(rows)


_RULE_LIST: List[Tuple[List[str], Callable]] = [
    (["IE.SANITY.001"], lambda r, c: _runner(r, c, rule_sanity_001_gross_deduction_consistency)),
    (["IE.SANITY.004"], lambda r, c: _runner(r, c, rule_sanity_004_deduction_breakdown_mismatch)),
    (["IE.SANITY.006"], lambda r, c: _runner(r, c, rule_sanity_006_net_inconsistency)),
    (["IE.SANITY.007"], lambda r, c: _runner(r, c, rule_sanity_007_net_upper_bound)),
    (["IE.SANITY.008"], lambda r, c: _runner(r, c, rule_sanity_008_net_equals_gross_with_deductions)),
    (["IE.SANITY.009"], lambda r, c: _runner(r, c, rule_sanity_009_deductions_exceed_gross)),
    (["IE.PAYSLIP.001"], lambda r, c: _runner(r, c, rule_payslip_001_missing_itemised)),
    (["IE.PAYSLIP.002"], lambda r, c: _runner(r, c, rule_payslip_002_gross_missing_or_zero)),
    (["IE.GROSS_NET.001"], lambda r, c: _runner(r, c, rule_gross_net_integrity)),
    (["IE.SANITY.002"], lambda r, c: _runner(r, c, rule_sanity_002_negative_or_zero_gross)),
    (["IE.SANITY.003"], lambda r, c: _runner(r, c, rule_sanity_003_impossible_or_negative_deductions)),
    (["IE.SANITY.005"], lambda r, c: _runner(r, c, rule_sanity_005_negative_net)),
    (["IE.PAYE.001"], lambda r, c: _runner(r, c, rule_paye_001_negative_or_impossible)),
    (["IE.PAYE.003"], lambda r, c: _runner(r, c, rule_paye_003_zero_when_taxable_present, True)),
    (["IE.PAYE.005"], lambda r, c: _runner(r, c, rule_paye_005_applied_when_taxable_zero)),
    (["IE.PAYE.004"], lambda r, c: _runner(r, c, rule_paye_004_negative)),
    (["IE.USC.004"], lambda r, c: _runner(r, c, rule_usc_004_negative)),
    (["IE.USC.006"], lambda r, c: _runner(r, c, rule_usc_006_missing_above_threshold, True)),
    (["IE.PRSI.003"], lambda r, c: _runner(r, c, rule_prsi_003_negative)),
    (["IE.PRSI.004"], lambda r, c: _runner(r, c, rule_prsi_004_applied_below_threshold, True)),
    (["IE.PRSI.005"], lambda r, c: _runner(r, c, rule_prsi_005_missing_above_threshold, True)),
    (["IE.ANOMALY.001", "IE.ANOMALY.002"], lambda r, c: _runner(r, c, rule_negative_or_zero_pay)),
    (["IE.USC.002"], lambda r, c: _runner(r, c, rule_usc_deterministic_bounds, True)),
    (["IE.PRSI.002"], lambda r, c: _runner(r, c, rule_prsi_deterministic_bounds, True)),
    (["IE.NET.002"], lambda r, c: _runner(r, c, rule_net_deterministic_upper_bound, True)),
    (["IE.PAYE.002"], lambda r, c: _runner(r, c, rule_paye_deterministic_bounds, True)),
    (["IE.MINWAGE.001"], lambda r, c: _runner(r, c, rule_minimum_wage_deterministic, True)),
    (["IE.AUTOENROL.001"], lambda r, c: _runner(r, c, rule_auto_enrolment_deterministic, True)),
    (["IE.USC.001"], lambda r, c: _runner(r, c, rule_usc_plausibility, True)),
    (["IE.PRSI.001"], lambda r, c: _runner(r, c, rule_prsi_plausibility_class_a, True)),
]
