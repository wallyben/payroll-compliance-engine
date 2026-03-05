"""Operational row rules: IE.MINWAGE.001, IE.PAY.001, IE.NET.003, IE.PRSI.001, IE.PRSI.004."""
from __future__ import annotations
from typing import List, Dict, Any
from core.normalize.schema import CanonicalPayrollRow
from core.rules.finding_utils import finding


def rule_ie_minwage_001(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.MINWAGE.001: gross_pay / hours < statutory_minimum_wage. Minimum wage configurable. HIGH."""
    mw_cfg = config.get("minimum_wage", {})
    min_rate = mw_cfg.get("hourly_rate")
    if min_rate is None:
        return []
    tol = 0.02
    out = []
    for r in rows:
        if r.hours is None or r.hours <= 0:
            continue
        effective_rate = r.gross_pay / r.hours
        if effective_rate + tol < min_rate:
            out.append(finding(
                "IE.MINWAGE.001",
                "HIGH",
                "Effective rate below statutory minimum wage",
                "gross_pay / hours < statutory_minimum_wage",
                evidence={"gross_pay": r.gross_pay, "hours": r.hours, "effective_rate": effective_rate, "minimum_wage": min_rate},
                suggestion="Verify hours and gross; ensure minimum wage compliance.",
                employee_refs=[r.employee_id],
                category="MINWAGE",
            ))
    return out


def rule_ie_pay_001(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.PAY.001: hours > 0 AND gross_pay == 0. HIGH."""
    out = []
    for r in rows:
        if (r.hours is not None and r.hours > 0) and (r.gross_pay is None or abs(r.gross_pay) < 0.01):
            out.append(finding(
                "IE.PAY.001",
                "HIGH",
                "Hours > 0 but gross_pay == 0",
                "hours > 0 AND gross_pay == 0",
                evidence={"hours": r.hours, "gross_pay": r.gross_pay},
                suggestion="Verify gross pay and hours; paid hours must have positive gross.",
                employee_refs=[r.employee_id],
                category="PAY",
            ))
    return out


def rule_ie_net_003(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.NET.003: gross_pay > 0 AND net_pay == 0. HIGH."""
    out = []
    for r in rows:
        if r.gross_pay > 0.01 and (r.net_pay is None or abs(r.net_pay) < 0.01):
            out.append(finding(
                "IE.NET.003",
                "HIGH",
                "Gross > 0 but net_pay == 0",
                "gross_pay > 0 AND net_pay == 0",
                evidence={"gross_pay": r.gross_pay, "net_pay": r.net_pay},
                suggestion="Verify net and deductions; net should not be zero when gross is positive.",
                employee_refs=[r.employee_id],
                category="NET",
            ))
    return out


def rule_ie_prsi_001(rows: List[CanonicalPayrollRow]) -> List[dict]:
    """IE.PRSI.001: prsi_class missing. HIGH."""
    out = []
    for r in rows:
        pc = getattr(r, "prsi_class", None)
        if pc is None or (isinstance(pc, str) and not pc.strip()):
            out.append(finding(
                "IE.PRSI.001",
                "HIGH",
                "PRSI class missing",
                "prsi_class missing",
                suggestion="Supply valid PRSI class from config.",
                employee_refs=[r.employee_id],
                category="PRSI",
            ))
    return out


def rule_ie_prsi_004(rows: List[CanonicalPayrollRow], config: Dict[str, Any]) -> List[dict]:
    """IE.PRSI.004: prsi_class not in valid_prsi_classes. Valid classes from config. HIGH."""
    prsi_cfg = config.get("prsi", {})
    valid = prsi_cfg.get("valid_prsi_classes", ["A", "B", "C", "D", "E", "H", "J", "K", "M", "P", "S"])
    valid_set = set(str(c).strip().upper() for c in valid)
    out = []
    for r in rows:
        pc = getattr(r, "prsi_class", None)
        if pc is None or (isinstance(pc, str) and not pc.strip()):
            continue  # IE.PRSI.001 handles missing
        if str(pc).strip().upper() not in valid_set:
            out.append(finding(
                "IE.PRSI.004",
                "HIGH",
                "PRSI class not in valid list",
                "prsi_class not in valid_prsi_classes",
                evidence={"prsi_class": pc, "valid_classes": list(valid_set)},
                suggestion="Use a valid PRSI class from configuration.",
                employee_refs=[r.employee_id],
                category="PRSI",
            ))
    return out
