"""PDF report generation for scan response. Uses reportlab.platypus."""
from io import BytesIO
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def build_scan_report_pdf(scan_response: Dict[str, Any]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name="Title", parent=styles["Heading1"], fontSize=16, spaceAfter=12)
    heading_style = ParagraphStyle(name="Heading", parent=styles["Heading2"], fontSize=12, spaceAfter=6)
    body_style = styles["Normal"]

    story = []
    story.append(Paragraph("Payroll Pre-Submission Risk Scan", title_style))
    story.append(Spacer(1, 6*mm))

    # Summary box
    s = scan_response.get("summary", {})
    summary_data = [
        ["Total findings", str(s.get("total_findings", 0))],
        ["Critical", str(s.get("critical", 0))],
        ["Warning", str(s.get("warning", 0))],
        ["Info", str(s.get("info", 0))],
        ["Overall", str(s.get("overall", "GREEN"))],
    ]
    t = Table(summary_data, colWidths=[80*mm, 40*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    story.append(Paragraph("Summary", heading_style))
    story.append(t)
    story.append(Spacer(1, 8*mm))

    def add_finding_section(title: str, findings: List[Dict]) -> None:
        story.append(Paragraph(title, heading_style))
        if not findings:
            story.append(Paragraph("None.", body_style))
        else:
            for f in findings[:50]:
                line = f"[{f.get('severity', '')}] {f.get('rule_id', '')} — {f.get('title', '')}"
                story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;")[:200], body_style))
        story.append(Spacer(1, 6*mm))

    add_finding_section("Auto-Enrolment Issues", scan_response.get("auto_enrolment_findings", []))
    add_finding_section("Revenue Issues", scan_response.get("revenue_findings", []))

    doc.build(story)
    return buf.getvalue()
