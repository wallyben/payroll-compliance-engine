"""PDF report generation for scan response. Uses reportlab.platypus."""
import hashlib
from io import BytesIO
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def _certificate_reference_hash(
    run_id: str, ruleset_version: str, employees_processed: int, validated_at: str
) -> str:
    """First 12 hex chars of SHA256(run_id|ruleset|employees|validated_at), formatted XXXX-XXXX-XXXX."""
    payload = f"{run_id}|{ruleset_version}|{employees_processed}|{validated_at}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{digest[0:4]}-{digest[4:8]}-{digest[8:12]}".upper()


def build_certificate_pdf(scan_response: Dict[str, Any]) -> bytes:
    """Generate a clean compliance certificate PDF when no findings (all_findings empty)."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=25*mm, leftMargin=25*mm, topMargin=25*mm, bottomMargin=25*mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="CertTitle", parent=styles["Heading1"], fontSize=18, spaceAfter=14, alignment=1
    )
    heading_style = ParagraphStyle(
        name="CertHeading", parent=styles["Heading2"], fontSize=14, spaceAfter=8, alignment=1
    )
    body_style = ParagraphStyle(
        name="CertBody", parent=styles["Normal"], fontSize=11, spaceAfter=6, alignment=1
    )
    small_style = ParagraphStyle(
        name="CertSmall", parent=styles["Normal"], fontSize=9, spaceAfter=4, alignment=1
    )
    footer_style = ParagraphStyle(
        name="CertFooter", parent=styles["Normal"], fontSize=8, spaceAfter=4,
        alignment=1, textColor=colors.grey
    )

    bureau = scan_response.get("bureau_summary", {})
    run_id = bureau.get("run_id", "—")
    ruleset = bureau.get("ruleset_version", "IE-2026.01")
    employees_processed = bureau.get("employees_impacted", 0)
    validated_at = scan_response.get("validated_at") or "—"
    cert_ref = _certificate_reference_hash(run_id, ruleset, employees_processed, validated_at)

    story = []
    story.append(Paragraph("Payroll Compliance Certificate", title_style))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Result: <b>PASSED</b>", heading_style))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"Ruleset: {ruleset}", body_style))
    story.append(Paragraph(f"Employees processed: {employees_processed}", body_style))
    story.append(Paragraph(f"Validation reference: {run_id}", body_style))
    story.append(Paragraph(f"Certificate reference: {cert_ref}", body_style))
    story.append(Paragraph(f"Validation timestamp: {validated_at}", body_style))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(
        "This certificate confirms that the submitted payroll file "
        "was validated using the IE-2026.01 rule library.",
        footer_style
    ))
    story.append(Paragraph(
        "This certificate reflects the payroll data provided at the time of validation.",
        footer_style
    ))
    doc.build(story)
    return buf.getvalue()


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
