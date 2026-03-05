"""Rule metadata registry for IE-2026.01. Deterministic, no inference."""
from __future__ import annotations
from typing import Dict, List
from pydantic import BaseModel


class RuleMeta(BaseModel):
    rule_id: str
    title: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    domain: str
    category: str
    description: str
    remediation: str
    exposure_weight: int
    ruleset_version: str


RULESET_VERSION = "IE-2026.01"

_ALLOWED_SEVERITY = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})


def _meta(
    rule_id: str,
    title: str,
    severity: str,
    domain: str,
    category: str,
    description: str,
    remediation: str,
    exposure_weight: int,
) -> RuleMeta:
    if severity not in _ALLOWED_SEVERITY:
        raise ValueError(f"severity must be one of {_ALLOWED_SEVERITY}")
    return RuleMeta(
        rule_id=rule_id,
        title=title,
        severity=severity,
        domain=domain,
        category=category,
        description=description,
        remediation=remediation,
        exposure_weight=exposure_weight,
        ruleset_version=RULESET_VERSION,
    )


# IE-2026.01 — 19 rules
_REGISTRY: List[RuleMeta] = [
    # --- Arithmetic Integrity ---
    _meta(
        "IE.NET.001",
        "Net pay exceeds gross pay",
        "CRITICAL",
        "arithmetic",
        "NET",
        "net_pay > gross_pay",
        "Reconcile net and gross; ensure deductions are not negative or mis-mapped.",
        100,
    ),
    _meta(
        "IE.NET.002",
        "Negative net pay",
        "CRITICAL",
        "arithmetic",
        "NET",
        "net_pay < 0",
        "Verify deductions and reversals; net pay must not be negative for standard pay.",
        100,
    ),
    _meta(
        "IE.DEDUCT.001",
        "Total deductions exceed gross pay",
        "HIGH",
        "arithmetic",
        "DEDUCT",
        "total_deductions > gross_pay",
        "Verify all deduction columns and signs; total deductions cannot exceed gross.",
        80,
    ),
    _meta(
        "IE.PENSION.002",
        "Pension contributions exceed 50% of gross",
        "MEDIUM",
        "arithmetic",
        "PENSION",
        "(pension_ee + pension_er) > gross_pay * 0.50",
        "Confirm pension rates and caps; combined pension should not exceed 50% of gross.",
        40,
    ),
    _meta(
        "IE.TOTALS.001",
        "File-level gross minus deductions != net",
        "CRITICAL",
        "arithmetic",
        "TOTALS",
        "SUM(gross_pay) - SUM(total_deductions) != SUM(net_pay)",
        "Reconcile file totals; allow small floating tolerance.",
        100,
    ),
    _meta(
        "IE.PAY.002",
        "Effective hourly rate exceeds 250",
        "MEDIUM",
        "arithmetic",
        "PAY",
        "gross_pay / hours > 250 (skip if hours == 0)",
        "Verify hours and gross; flag implausible rates for review.",
        30,
    ),
    # --- Operational Errors ---
    _meta(
        "IE.MINWAGE.001",
        "Effective rate below statutory minimum wage",
        "HIGH",
        "operational",
        "MINWAGE",
        "gross_pay / hours < statutory_minimum_wage",
        "Verify hours and gross; ensure minimum wage compliance.",
        70,
    ),
    _meta(
        "IE.PAY.001",
        "Hours > 0 but gross_pay == 0",
        "HIGH",
        "operational",
        "PAY",
        "hours > 0 AND gross_pay == 0",
        "Verify gross pay and hours; paid hours must have positive gross.",
        70,
    ),
    _meta(
        "IE.NET.003",
        "Gross > 0 but net_pay == 0",
        "HIGH",
        "operational",
        "NET",
        "gross_pay > 0 AND net_pay == 0",
        "Verify net and deductions; net should not be zero when gross is positive.",
        70,
    ),
    _meta(
        "IE.DATA.001",
        "Duplicate employee within payroll file",
        "HIGH",
        "operational",
        "DATA",
        "Duplicate employee_id in same file",
        "Deduplicate rows per employee per period.",
        60,
    ),
    _meta(
        "IE.PRSI.001",
        "PRSI class missing",
        "HIGH",
        "operational",
        "PRSI",
        "prsi_class missing",
        "Supply valid PRSI class from config.",
        70,
    ),
    _meta(
        "IE.PRSI.004",
        "PRSI class not in valid list",
        "HIGH",
        "operational",
        "PRSI",
        "prsi_class not in valid_prsi_classes",
        "Use a valid PRSI class from configuration.",
        70,
    ),
    # --- Compliance Configuration ---
    _meta(
        "IE.USC.001",
        "USC deducted below exemption threshold",
        "MEDIUM",
        "compliance",
        "USC",
        "gross_pay < usc_exemption_threshold AND usc_deduction > 0",
        "Do not apply USC below exemption threshold.",
        50,
    ),
    _meta(
        "IE.USC.002",
        "USC zero above threshold",
        "MEDIUM",
        "compliance",
        "USC",
        "gross_pay > usc_threshold AND usc_deduction == 0",
        "Apply USC when pay exceeds threshold.",
        50,
    ),
    _meta(
        "IE.AUTOENROL.001",
        "Eligible for auto-enrolment but no pension",
        "HIGH",
        "compliance",
        "AUTOENROL",
        "age 23-60, earnings above threshold, pension_ee==0, pension_er==0",
        "Enrol eligible employees in pension scheme.",
        70,
    ),
    _meta(
        "IE.AUTOENROL.002",
        "Auto-enrolment pension below expected minimum",
        "HIGH",
        "compliance",
        "AUTOENROL",
        "eligible_for_auto_enrolment AND contribution < expected minimum",
        "Ensure minimum contribution for auto-enrolled employees.",
        70,
    ),
    _meta(
        "IE.BIK.001",
        "Car allowance with zero BIK value",
        "MEDIUM",
        "compliance",
        "BIK",
        "allowance_type == 'car' AND bik_value == 0",
        "Report BIK for car allowance.",
        40,
    ),
    _meta(
        "IE.PRSI.003",
        "PRSI Class A with weekly earnings below threshold",
        "LOW",
        "compliance",
        "PRSI",
        "prsi_class == 'A' AND weekly_earnings < threshold",
        "Verify PRSI class and earnings threshold.",
        20,
    ),
    _meta(
        "IE.DATA.002",
        "Missing critical fields",
        "CRITICAL",
        "compliance",
        "DATA",
        "employee_id OR gross_pay OR net_pay missing",
        "Supply required fields for every row.",
        100,
    ),
]

REGISTRY: Dict[str, RuleMeta] = {m.rule_id: m for m in _REGISTRY}


def get_meta(rule_id: str) -> RuleMeta | None:
    return REGISTRY.get(rule_id)


def all_rule_ids() -> List[str]:
    """Deterministic order of rule IDs (by domain then rule_id)."""
    order = [m.rule_id for m in _REGISTRY]
    return list(order)
