from __future__ import annotations

from typing import Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_pdf(
    path: str,
    company: str,
    ruleset_version: str,
    risk_score: int,
    findings: List[Dict],
    severity_summary: Optional[Dict[str, int]] = None,
    exposure_total: Optional[float] = None,
    risk_band: Optional[str] = None,
) -> None:
    """Render a deterministic compliance report PDF.

    Parameters that were added in Phase 5 (severity_summary, exposure_total,
    risk_band) are optional so that existing callers continue to work unchanged.
    When supplied they are rendered in the report header section.
    """
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "Payroll Compliance Report (v1)")
    y -= 8 * mm

    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Company: {company}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Ruleset: {ruleset_version}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Risk Score: {risk_score}/100")
    y -= 5 * mm

    if risk_band is not None:
        c.drawString(20 * mm, y, f"Risk Band: {risk_band}")
        y -= 5 * mm

    if severity_summary is not None:
        high = severity_summary.get("HIGH", 0)
        medium = severity_summary.get("MEDIUM", 0)
        low = severity_summary.get("LOW", 0)
        total = severity_summary.get("TOTAL", high + medium + low)
        c.drawString(
            20 * mm, y,
            f"Severity: HIGH {high} | MEDIUM {medium} | LOW {low} | TOTAL {total}",
        )
        y -= 5 * mm

    if exposure_total is not None:
        c.drawString(20 * mm, y, f"Total Exposure: EUR {exposure_total:,.2f}")
        y -= 5 * mm

    y -= 5 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, f"Findings ({len(findings)} total)")
    y -= 7 * mm

    c.setFont("Helvetica", 9)
    for f in findings[:200]:
        line = f"[{f['severity']}] {f['rule_id']} \u2014 {f['title']}"
        c.drawString(20 * mm, y, line[:120])
        y -= 4.5 * mm
        if y < 20 * mm:
            c.showPage()
            y = height - 20 * mm
            c.setFont("Helvetica", 9)

    c.save()
