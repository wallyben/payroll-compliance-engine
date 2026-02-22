"""Upload-based payroll risk scanner. No auth, no DB writes."""
import io
import json
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from apps.api.config_loader import load_rules_config
from apps.api.helpers.scan_summary import build_scan_summary, split_findings
from apps.api.helpers.report_builder import build_scan_report_pdf
from core.normalize.mapper import normalize
from core.rules.engine import run_all

router = APIRouter()

# Profile file on disk is bureau_wedge.json
SCAN_PROFILE = "bureau_wedge"


def _csv_to_mapping(df: pd.DataFrame) -> Dict[str, str]:
    """Build canonical mapping from CSV columns. Uses identity for columns that match canonical names."""
    required = {"employee_id", "gross_pay", "net_pay"}
    canon_fields = {"employee_id", "employee_name", "ppsn", "pay_date", "period_start", "period_end",
                    "gross_pay", "net_pay", "paye", "usc", "prsi_ee", "prsi_er", "pension_ee", "pension_er", "hours"}
    mapping = {}
    for col in df.columns:
        c = (col or "").strip()
        if c in canon_fields:
            mapping[c] = col
    missing = required - set(mapping.keys())
    if missing:
        raise ValueError(f"CSV must include columns: {list(required)}. Found: {list(df.columns)}")
    return mapping


@router.post("/", response_model=Dict[str, Any])
def scan_upload(file: UploadFile = File(...)):
    """POST /scan: CSV upload -> run engine with BUREAU_WEDGE profile -> return summary and findings."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload must be a CSV file")
    content = file.file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")
    if df.empty:
        raise HTTPException(status_code=400, detail="CSV has no rows")
    try:
        mapping = _csv_to_mapping(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        rows, _ = normalize(df, mapping)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not rows:
        raise HTTPException(status_code=400, detail="No valid rows after normalization")
    config = load_rules_config()
    config["scan_profile"] = SCAN_PROFILE
    findings = run_all(rows, config)
    summary = build_scan_summary(findings)
    auto_enrolment_findings, revenue_findings = split_findings(findings)
    return {
        "summary": summary,
        "auto_enrolment_findings": auto_enrolment_findings,
        "revenue_findings": revenue_findings,
        "all_findings": findings,
    }


@router.get("/report")
async def scan_report(request: Request):
    """GET /scan/report: JSON body (same shape as POST /scan response) -> PDF stream."""
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="JSON body required with scan response shape")
    try:
        body = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    pdf_bytes = build_scan_report_pdf(body)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scan_report.pdf"},
    )

