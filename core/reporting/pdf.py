from __future__ import annotations
from typing import List, Dict
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

def build_pdf(path: str, company: str, ruleset_version: str, risk_score: int, findings: List[Dict]) -> None:
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    y = height - 20*mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20*mm, y, "Payroll Compliance Report (v1)")
    y -= 8*mm

    c.setFont("Helvetica", 10)
    c.drawString(20*mm, y, f"Company: {company}")
    y -= 5*mm
    c.drawString(20*mm, y, f"Ruleset: {ruleset_version}")
    y -= 5*mm
    c.drawString(20*mm, y, f"Risk Score: {risk_score}/100")
    y -= 10*mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20*mm, y, "Findings")
    y -= 7*mm

    c.setFont("Helvetica", 9)
    for f in findings[:200]:
        line = f"[{f['severity']}] {f['rule_id']} — {f['title']}"
        c.drawString(20*mm, y, line[:120])
        y -= 4.5*mm
        if y < 20*mm:
            c.showPage()
            y = height - 20*mm
            c.setFont("Helvetica", 9)

    c.save()
