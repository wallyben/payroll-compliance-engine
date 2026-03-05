"""Phase 4 Gate 2: Exposure report from findings. Deterministic, no invented amounts."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExposureCategoryBreakdown:
    category: str
    underpayment_total: float
    overpayment_total: float
    employees_impacted: int
    quantifiable_findings: int
    non_quantifiable_findings: int


@dataclass
class ExposureRuleBreakdown:
    rule_id: str
    finding_count: int
    exposure_weight: int
    total_amount_impact: float


@dataclass
class ExposureReport:
    underpayment_total: float
    overpayment_total: float
    categories: list[ExposureCategoryBreakdown]
    employees_impacted: int
    quantifiable_findings: int
    non_quantifiable_findings: int
    confidence_level: str  # HIGH | MEDIUM | LOW
    total_exposure: float = 0.0  # underpayment_total + overpayment_total
    severity_counts: dict[str, int] = field(default_factory=dict)
    rule_breakdown: list[ExposureRuleBreakdown] = field(default_factory=list)


def _category(f: dict[str, Any]) -> str:
    return f.get("category") or f.get("rule_id") or "UNKNOWN"


def _amount(f: dict[str, Any]) -> float | None:
    v = f.get("amount_impact")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _employee_refs(f: dict[str, Any]) -> list[str]:
    refs = f.get("employee_refs")
    if not isinstance(refs, list):
        return []
    return [str(r) for r in refs]


def _exposure_weight(rule_id: str) -> int:
    try:
        from core.rules.registry import get_meta
        meta = get_meta(rule_id)
        return meta.exposure_weight if meta else 1
    except Exception:
        return 1


def build_exposure_report(findings: list[dict[str, Any]]) -> ExposureReport:
    """Build exposure report from findings. Group by category; stable order by category name."""
    # Group by category
    by_cat: dict[str, list[dict[str, Any]]] = {}
    severity_counts: dict[str, int] = {}
    by_rule: dict[str, list[dict[str, Any]]] = {}
    for f in findings:
        cat = _category(f)
        by_cat.setdefault(cat, []).append(f)
        sev = f.get("severity") or "UNKNOWN"
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        rid = f.get("rule_id") or "UNKNOWN"
        by_rule.setdefault(rid, []).append(f)

    categories_out: list[ExposureCategoryBreakdown] = []
    report_under = 0.0
    report_over = 0.0
    all_employee_ids: set[str] = set()
    report_quant = 0
    report_non_quant = 0

    for cat in sorted(by_cat.keys()):
        group = by_cat[cat]
        under = 0.0
        over = 0.0
        quant = 0
        non_quant = 0
        emp_ids: set[str] = set()
        for f in group:
            refs = _employee_refs(f)
            emp_ids.update(refs)
            all_employee_ids.update(refs)
            amt = _amount(f)
            if amt is not None:
                quant += 1
                if amt < 0:
                    under += abs(amt)
                elif amt > 0:
                    over += amt
            else:
                non_quant += 1
        report_under += under
        report_over += over
        report_quant += quant
        report_non_quant += non_quant
        categories_out.append(
            ExposureCategoryBreakdown(
                category=cat,
                underpayment_total=under,
                overpayment_total=over,
                employees_impacted=len(emp_ids),
                quantifiable_findings=quant,
                non_quantifiable_findings=non_quant,
            )
        )

    total_exposure = report_under + report_over
    rule_breakdown_out: list[ExposureRuleBreakdown] = []
    for rid in sorted(by_rule.keys()):
        group = by_rule[rid]
        weight = _exposure_weight(rid)
        total_amt = 0.0
        for f in group:
            amt = _amount(f)
            if amt is not None:
                total_amt += abs(amt)
        rule_breakdown_out.append(
            ExposureRuleBreakdown(
                rule_id=rid,
                finding_count=len(group),
                exposure_weight=weight,
                total_amount_impact=total_amt,
            )
        )

    total_findings = report_quant + report_non_quant
    if total_findings == 0 or report_non_quant == 0:
        confidence_level = "HIGH"
    elif report_non_quant / total_findings <= 0.20:
        confidence_level = "MEDIUM"
    else:
        confidence_level = "LOW"

    return ExposureReport(
        underpayment_total=report_under,
        overpayment_total=report_over,
        categories=categories_out,
        employees_impacted=len(all_employee_ids),
        quantifiable_findings=report_quant,
        non_quantifiable_findings=report_non_quant,
        confidence_level=confidence_level,
        total_exposure=total_exposure,
        severity_counts=severity_counts,
        rule_breakdown=rule_breakdown_out,
    )
