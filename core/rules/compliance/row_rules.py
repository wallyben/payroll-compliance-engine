"""Compliance row rules: IE.USC.001, IE.USC.002, IE.AUTOENROL.001, IE.AUTOENROL.002, IE.BIK.001, IE.PRSI.003."""
from __future__ import annotations
from typing import List, Dict, Any
from core.normalize.schema import CanonicalPayrollRow
from core.rules.finding_utils import finding


def _annualise_gross(r: CanonicalPayrollRow) -> float:
    """Conservative annualisation: assume monthly if gross looks monthly."""
    if r.gross_pay < 2000:
        return r.gross_pay * 52  # weekly
    return r.gross_pay * 12  # monthly


def rule_ie_usc_001(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.USC.001: gross_pay < usc_exemption_threshold AND usc_deduction > 0. MEDIUM."""
    usc_cfg = config.get("usc", {})
    exemption = usc_cfg.get("exemption_limit", 13000)
    out = []
    for r in rows:
        annual = _annualise_gross(r)
        if annual < exemption and (r.usc or 0) > 0.01:
            out.append(finding(
                "IE.USC.001",
                "MEDIUM",
                "USC deducted below exemption threshold",
                "gross_pay < usc_exemption_threshold AND usc_deduction > 0",
                evidence={"annualised_gross": annual, "exemption_limit": exemption, "usc": r.usc},
                suggestion="Do not apply USC below exemption threshold.",
                employee_refs=[r.employee_id],
                category="USC",
            ))
    return out


def rule_ie_usc_002(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.USC.002: gross_pay > usc_threshold AND usc_deduction == 0. MEDIUM."""
    usc_cfg = config.get("usc", {})
    threshold = usc_cfg.get("exemption_limit", 13000)  # same as threshold above which USC due
    out = []
    for r in rows:
        annual = _annualise_gross(r)
        if annual > threshold + 1 and (r.usc is None or abs(r.usc) < 0.01):
            out.append(finding(
                "IE.USC.002",
                "MEDIUM",
                "USC zero above threshold",
                "gross_pay > usc_threshold AND usc_deduction == 0",
                evidence={"annualised_gross": annual, "usc_threshold": threshold},
                suggestion="Apply USC when pay exceeds threshold.",
                employee_refs=[r.employee_id],
                category="USC",
            ))
    return out


def rule_ie_autoenrol_001(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.AUTOENROL.001: age 23-60, earnings above threshold, pension_ee==0, pension_er==0. HIGH."""
    ae_cfg = config.get("auto_enrolment", {}).get("eligibility", {})
    age_min = ae_cfg.get("age_min", 23)
    age_max = ae_cfg.get("age_max", 60)
    earnings_min = ae_cfg.get("annual_earnings_min", 20000)
    out = []
    for r in rows:
        annual = _annualise_gross(r)
        if annual < earnings_min:
            continue
        age = getattr(r, "age", None)
        if age is not None and (age < age_min or age > age_max):
            continue
        if (r.pension_ee or 0) > 0.01 or (r.pension_er or 0) > 0.01:
            continue
        # Eligible: earnings above threshold, age in range (or unknown), no pension
        if age is None:
            # Cannot determine eligibility without age; skip or flag as data missing
            continue
        out.append(finding(
            "IE.AUTOENROL.001",
            "HIGH",
            "Eligible for auto-enrolment but no pension",
            "age 23-60, earnings above threshold, pension_ee==0, pension_er==0",
            evidence={"age": age, "annualised_earnings": annual, "threshold": earnings_min},
            suggestion="Enrol eligible employees in pension scheme.",
            employee_refs=[r.employee_id],
            category="AUTOENROL",
        ))
    return out


def rule_ie_autoenrol_002(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.AUTOENROL.002: eligible_for_auto_enrolment AND pension contribution < expected minimum. HIGH."""
    ae_cfg = config.get("auto_enrolment", {}).get("eligibility", {})
    age_min = ae_cfg.get("age_min", 23)
    age_max = ae_cfg.get("age_max", 60)
    earnings_min = ae_cfg.get("annual_earnings_min", 20000)
    min_rate = ae_cfg.get("minimum_contribution_rate", 0.01)  # 1% default
    out = []
    for r in rows:
        annual = _annualise_gross(r)
        if annual < earnings_min:
            continue
        age = getattr(r, "age", None)
        if age is None or age < age_min or age > age_max:
            continue
        total_pension = (r.pension_ee or 0) + (r.pension_er or 0)
        if total_pension < 0.01:
            continue  # no pension at all -> IE.AUTOENROL.001
        expected_min = r.gross_pay * min_rate
        if total_pension < expected_min - 0.01:
            out.append(finding(
                "IE.AUTOENROL.002",
                "HIGH",
                "Auto-enrolment pension below expected minimum",
                "eligible_for_auto_enrolment AND contribution < expected minimum",
                evidence={"pension_total": total_pension, "expected_minimum": expected_min, "min_rate": min_rate},
                suggestion="Ensure minimum contribution for auto-enrolled employees.",
                employee_refs=[r.employee_id],
                category="AUTOENROL",
            ))
    return out


def rule_ie_bik_001(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.BIK.001: allowance_type == 'car' AND bik_value == 0. MEDIUM."""
    out = []
    for r in rows:
        at = getattr(r, "allowance_type", None)
        bik = getattr(r, "bik_value", None)
        if at is None or str(at).strip().lower() != "car":
            continue
        if bik is not None and abs(bik) > 0.01:
            continue
        out.append(finding(
            "IE.BIK.001",
            "MEDIUM",
            "Car allowance with zero BIK value",
            "allowance_type == 'car' AND bik_value == 0",
            suggestion="Report BIK for car allowance.",
            employee_refs=[r.employee_id],
            category="BIK",
        ))
    return out


def rule_ie_prsi_003(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.PRSI.003: prsi_class == 'A' AND weekly_earnings < threshold. LOW."""
    prsi_cfg = config.get("prsi", {}).get("class_a", {})
    threshold = prsi_cfg.get("weekly_threshold_lower", 352.0)
    out = []
    for r in rows:
        pc = getattr(r, "prsi_class", None)
        if pc is None or str(pc).strip().upper() != "A":
            continue
        weekly = getattr(r, "weekly_earnings", None)
        if weekly is None:
            # Derive from gross if weekly not present
            if r.gross_pay < 2000:
                weekly = r.gross_pay
            else:
                weekly = r.gross_pay / 4.33
        if weekly >= threshold - 0.01:
            continue
        out.append(finding(
            "IE.PRSI.003",
            "LOW",
            "PRSI Class A with weekly earnings below threshold",
            "prsi_class == 'A' AND weekly_earnings < threshold",
            evidence={"weekly_earnings": weekly, "threshold": threshold},
            suggestion="Verify PRSI class and earnings threshold.",
            employee_refs=[r.employee_id],
            category="PRSI",
        ))
    return out
