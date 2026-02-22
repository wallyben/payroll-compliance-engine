from __future__ import annotations
from typing import List, Dict, Any
from core.normalize.schema import CanonicalPayrollRow

def _finding(rule_id: str, severity: str, title: str, description: str, **kw) -> dict:
    out = {
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        "description": description,
        "evidence": kw.get("evidence", {}),
        "suggestion": kw.get("suggestion", ""),
        "amount_impact": kw.get("amount_impact"),
        "employee_refs": kw.get("employee_refs", []),
    }
    return out


def rule_gross_net_integrity(rows: List[CanonicalPayrollRow]) -> List[dict]:
    findings = []
    bad = []
    for r in rows:
        if r.gross_pay < 0 or r.net_pay > r.gross_pay + 0.01:
            bad.append(r.employee_id)
    if bad:
        findings.append(_finding(
            "IE.GROSS_NET.001",
            "HIGH",
            "Gross/Net integrity issue",
            "One or more rows have net pay > gross pay or negative gross pay.",
            evidence={"count": len(bad)},
            suggestion="Check adjustments, reversals, and deduction sign conventions in your payroll export.",
            employee_refs=bad[:200]
        ))
    return findings


def rule_sanity_002_negative_or_zero_gross(rows: List[CanonicalPayrollRow]) -> List[dict]:
    findings = []
    bad = [r.employee_id for r in rows if r.gross_pay <= 0.0]
    if bad:
        findings.append(_finding(
            "IE.SANITY.002",
            "HIGH",
            "Negative or zero gross pay",
            "One or more rows have gross pay <= 0.",
            evidence={"count": len(bad)},
            suggestion="Verify gross pay values; negative or zero gross may indicate data or mapping errors.",
            employee_refs=bad[:200],
        ))
    return findings


def rule_sanity_003_impossible_or_negative_deductions(rows: List[CanonicalPayrollRow]) -> List[dict]:
    findings = []
    bad = [
        r.employee_id for r in rows
        if r.paye < -0.01 or r.usc < -0.01 or r.prsi_ee < -0.01 or r.prsi_er < -0.01 or r.pension_ee < -0.01
    ]
    if bad:
        findings.append(_finding(
            "IE.SANITY.003",
            "HIGH",
            "Impossible or negative deduction values",
            "One or more rows have negative PAYE, USC, PRSI, or pension deduction values.",
            evidence={"count": len(bad)},
            suggestion="Verify deduction columns; negative values may indicate refunds or mapping errors.",
            employee_refs=bad[:200],
        ))
    return findings


def rule_sanity_005_negative_net(rows: List[CanonicalPayrollRow]) -> List[dict]:
    findings = []
    bad = [r.employee_id for r in rows if r.net_pay < -0.01]
    if bad:
        findings.append(_finding(
            "IE.SANITY.005",
            "HIGH",
            "Negative net pay detection",
            "One or more rows have negative net pay.",
            evidence={"count": len(bad)},
            suggestion="Verify net pay and deductions; negative net may indicate reversals or over-deduction.",
            employee_refs=bad[:200],
        ))
    return findings


def rule_negative_or_zero_pay(rows: List[CanonicalPayrollRow]) -> List[dict]:
    findings = []
    neg = [r.employee_id for r in rows if r.net_pay < -0.01]
    if neg:
        findings.append(_finding(
            "IE.ANOMALY.001",
            "MEDIUM",
            "Negative net pay detected",
            "Negative net pay often indicates a reversal, over-deduction, or incorrect adjustment sign.",
            evidence={"count": len(neg)},
            suggestion="Review affected employees for reversals and ensure deduction/refund signs are correct.",
            employee_refs=neg[:200],
        ))
    zero_gross = [r.employee_id for r in rows if abs(r.gross_pay) < 0.01 and abs(r.net_pay) > 0.01]
    if zero_gross:
        findings.append(_finding(
            "IE.ANOMALY.002",
            "MEDIUM",
            "Non-zero net with zero gross",
            "Net pay present with zero gross is unusual and can indicate import/mapping errors.",
            evidence={"count": len(zero_gross)},
            suggestion="Re-check column mapping and confirm gross/net columns are correct.",
            employee_refs=zero_gross[:200],
        ))
    return findings


# ✅ FIXED Progressive USC Calculation
def _usc_calc_annual(income: float, usc_cfg: Dict[str, Any]) -> float:
    bands = usc_cfg["bands"]
    remaining = income
    total = 0.0
    prev_cap = 0.0

    for b in bands:
        cap = b["cap"]
        rate = b["rate"]

        if remaining <= 0:
            break

        if cap is None:
            total += remaining * rate
            break

        band_width = cap - prev_cap
        taxable = min(remaining, band_width)

        if taxable > 0:
            total += taxable * rate
            remaining -= taxable

        prev_cap = cap

    return total


def rule_usc_plausibility(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    usc_cfg = cfg["usc"]
    findings = []
    flagged = []
    for r in rows:
        if r.usc <= 0:
            continue
        annual = r.gross_pay * (52 if r.gross_pay < 2000 else 12)
        if annual <= usc_cfg["exemption_limit"]:
            flagged.append(r.employee_id)
            continue
        expected_annual = _usc_calc_annual(annual, usc_cfg)
        expected_period = expected_annual / (52 if r.gross_pay < 2000 else 12)
        if not (0.65 * expected_period <= r.usc <= 1.35 * expected_period):
            flagged.append(r.employee_id)
    if flagged:
        findings.append(_finding(
            "IE.USC.001",
            "LOW",
            "USC plausibility outliers",
            "USC appears high/low versus a simple band-based estimate.",
            evidence={"count": len(flagged)},
            suggestion="Verify USC column mapping and review cumulative vs non-cumulative settings.",
            employee_refs=flagged[:200],
        ))
    return findings


def rule_prsi_plausibility_class_a(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    prsi = cfg["prsi"]["class_a"]
    findings = []
    flagged = []
    for r in rows:
        if r.prsi_ee <= 0 and r.prsi_er <= 0:
            continue
        weekly = r.gross_pay if r.gross_pay < 2000 else r.gross_pay / 4.33
        employer_rate = prsi["employer_rate_higher"] if weekly > prsi["weekly_threshold_for_higher"] else prsi["employer_rate_lower"]
        ee_rate = prsi["employee_rate_pre_2026_10_01"]
        expected_ee = r.gross_pay * ee_rate
        expected_er = r.gross_pay * employer_rate
        if r.prsi_ee > 0 and not (0.6*expected_ee <= r.prsi_ee <= 1.4*expected_ee):
            flagged.append(r.employee_id)
        if r.prsi_er > 0 and not (0.6*expected_er <= r.prsi_er <= 1.4*expected_er):
            flagged.append(r.employee_id)
    flagged = list(dict.fromkeys(flagged))
    if flagged:
        findings.append(_finding(
            "IE.PRSI.001",
            "LOW",
            "PRSI plausibility outliers (Class A)",
            "PRSI appears high/low versus typical Class A rates.",
            evidence={"count": len(flagged)},
            suggestion="Confirm PRSI class and verify PRSI column mapping.",
            employee_refs=flagged[:200],
        ))
    return findings

def rule_prsi_deterministic_bounds(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    prsi_cfg = cfg["prsi"]["class_a"]

    max_employee_rate = prsi_cfg["employee_rate_pre_2026_10_01"]
    max_employer_rate = prsi_cfg["employer_rate_higher"]

    findings = []
    flagged = []

    for r in rows:
        # Non-negative enforcement
        if r.prsi_ee < 0 or r.prsi_er < 0:
            flagged.append(r.employee_id)
            continue

        # Cannot exceed gross
        if r.prsi_ee > r.gross_pay or r.prsi_er > r.gross_pay:
            flagged.append(r.employee_id)
            continue

        # Deterministic statutory ceiling
        if r.prsi_ee > r.gross_pay * max_employee_rate:
            flagged.append(r.employee_id)

        if r.prsi_er > r.gross_pay * max_employer_rate:
            flagged.append(r.employee_id)

    flagged = list(dict.fromkeys(flagged))

    if flagged:
        findings.append(_finding(
            "IE.PRSI.002",
            "HIGH",
            "PRSI deterministic bounds breach",
            "PRSI exceeds statutory maximum bounds or contains invalid negative values.",
            evidence={"count": len(flagged)},
            suggestion="Verify PRSI values and ensure statutory rates are correctly applied.",
            employee_refs=flagged[:200],
        ))

    return findings

def rule_usc_deterministic_bounds(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    findings = []
    flagged = []

    for r in rows:
        # Non-negative
        if r.usc < 0:
            flagged.append(r.employee_id)
            continue

        # If gross is zero/negative, USC must be zero
        if r.gross_pay <= 0 and r.usc > 0.01:
            flagged.append(r.employee_id)
            continue

        # USC cannot exceed gross pay in the row
        if r.usc > r.gross_pay + 0.01:
            flagged.append(r.employee_id)

    flagged = list(dict.fromkeys(flagged))

    if flagged:
        findings.append(_finding(
            "IE.USC.002",
            "HIGH",
            "USC deterministic bounds breach",
            "USC contains invalid negative values, exceeds gross pay, or is non-zero when gross pay is zero/negative.",
            evidence={"count": len(flagged)},
            suggestion="Verify USC values and column mapping; check for sign errors or deductions exceeding pay.",
            employee_refs=flagged[:200],
        ))

    return findings

def rule_net_deterministic_upper_bound(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    findings = []
    flagged = []

    # Deterministic rounding tolerance (cents + tiny float noise)
    tol = 0.02

    for r in rows:
        known_deductions = (r.paye or 0.0) + (r.usc or 0.0) + (r.prsi_ee or 0.0) + (r.pension_ee or 0.0)
        max_possible_net = r.gross_pay - known_deductions

        # Net cannot exceed gross minus known deductions (other deductions would only reduce net further)
        if r.net_pay > max_possible_net + tol:
            flagged.append(r.employee_id)

    flagged = list(dict.fromkeys(flagged))

    if flagged:
        findings.append(_finding(
            "IE.NET.002",
            "HIGH",
            "Net pay exceeds gross minus known deductions",
            "Net pay is higher than gross pay minus PAYE/USC/PRSI(EE)/pension(EE). This is arithmetically inconsistent unless a deduction field is mapped with the wrong sign or incorrect column mapping occurred.",
            evidence={"count": len(flagged)},
            suggestion="Verify that PAYE/USC/PRSI(EE)/pension(EE) are mapped correctly and have the correct sign conventions; confirm gross/net columns are not swapped.",
            employee_refs=flagged[:200],
        ))

    return findings

def rule_paye_deterministic_bounds(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    tax_cfg = cfg.get("income_tax", {})
    higher_rate = tax_cfg.get("higher_rate", 0.4)

    findings = []
    flagged = []

    tol = 0.02  # rounding tolerance

    for r in rows:
        # Non-negative
        if r.paye < 0:
            flagged.append(r.employee_id)
            continue

        # If gross <= 0, PAYE must be zero
        if r.gross_pay <= 0 and r.paye > tol:
            flagged.append(r.employee_id)
            continue

        # Cannot exceed gross
        if r.paye > r.gross_pay + tol:
            flagged.append(r.employee_id)
            continue

        # Cannot exceed gross taxed fully at higher rate
        if r.paye > r.gross_pay * higher_rate + tol:
            flagged.append(r.employee_id)

    flagged = list(dict.fromkeys(flagged))

    if flagged:
        findings.append(_finding(
            "IE.PAYE.002",
            "HIGH",
            "PAYE deterministic bounds breach",
            "PAYE exceeds statutory upper bounds or contains invalid negative values.",
            evidence={"count": len(flagged)},
            suggestion="Verify PAYE values and ensure correct tax rate application and column mapping.",
            employee_refs=flagged[:200],
        ))

    return findings

def rule_auto_enrolment_deterministic(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    ae_cfg = cfg.get("auto_enrolment", {}).get("eligibility", {})
    earnings_min = ae_cfg.get("annual_earnings_min")

    if earnings_min is None:
        return []

    findings = []
    flagged = []

    for r in rows:
        # Conservative annualisation (monthly baseline)
        annualised = r.gross_pay * 12

        # If below threshold but pension deducted → flag
        if annualised < earnings_min and r.pension_ee > 0:
            flagged.append(r.employee_id)

    flagged = list(dict.fromkeys(flagged))

    if flagged:
        findings.append(_finding(
            "IE.AUTOENROL.001",
            "HIGH",
            "Auto-enrolment eligibility breach (deterministic)",
            "Pension contribution present but annualised earnings are below statutory eligibility threshold.",
            evidence={"count": len(flagged)},
            suggestion="Verify employee eligibility for auto-enrolment and confirm pension deduction logic.",
            employee_refs=flagged[:200],
        ))

    return findings

def rule_minimum_wage_deterministic(rows: List[CanonicalPayrollRow], cfg: Dict[str, Any]) -> List[dict]:
    mw_cfg = cfg.get("minimum_wage", {})
    min_rate = mw_cfg.get("hourly_rate")

    if min_rate is None:
        return []

    findings = []
    flagged = []

    tol = 0.02

    for r in rows:
        if r.hours is None:
            continue

        if r.hours <= 0:
            continue

        effective_rate = r.gross_pay / r.hours

        if effective_rate + tol < min_rate:
            flagged.append(r.employee_id)

    flagged = list(dict.fromkeys(flagged))

    if flagged:
        findings.append(_finding(
            "IE.MINWAGE.001",
            "HIGH",
            "Minimum wage breach (deterministic)",
            "Gross pay divided by reported hours is below statutory minimum wage.",
            evidence={"count": len(flagged)},
            suggestion="Verify hours worked, gross pay components, and minimum wage compliance.",
            employee_refs=flagged[:200],
        ))

    return findings
