from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from pathlib import Path

from apps.api.db import get_db
from apps.api import models
from apps.api.schemas import RunOut, Finding
from apps.api.deps import require_role
from apps.api.settings import settings
from apps.api.helpers import aggregate_severity_summary
from apps.api.config_loader import load_rules_config, REPORTS_DIR, report_path_for_run
from fastapi.responses import FileResponse

from core.ingest.loader import load_table
from core.normalize.mapper import normalize
from core.rules.engine import run_all
from core.scoring.risk import score_bundle
from core.reporting.pdf import build_pdf

router = APIRouter()


@router.post("", response_model=RunOut)
def create_run(
    upload_id: int,
    mapping_id: int,
    company: str = "Unknown",
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "auditor")),
):
    upload = db.query(models.Upload).get(upload_id)
    mapping = db.query(models.Mapping).get(mapping_id)

    if not upload or not mapping or mapping.upload_id != upload_id:
        raise HTTPException(status_code=404, detail="Upload/mapping not found or mismatched")

    cfg = load_rules_config()

    # Load file
    df = load_table(upload.stored_path)

    # Apply mapping + normalization
    mapping_dict = json.loads(mapping.mapping_json)
    rows, invalid_rows = normalize(df, mapping_dict)

    # Run rules only on valid rows
    findings = run_all(rows, cfg)
    bundle = score_bundle(findings)

    severity_summary = aggregate_severity_summary(findings)

    # Persist run
    run = models.Run(
        upload_id=upload_id,
        mapping_id=mapping_id,
        ruleset_version=settings.ruleset_version,
        findings_json=json.dumps({
            "score_bundle": bundle,
            "findings": findings,
        }),
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    # Build PDF report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = REPORTS_DIR / f"run_{run.id}.pdf"

    build_pdf(
        str(pdf_path),
        company=company,
        ruleset_version=settings.ruleset_version,
        risk_score=bundle["compliance_score"],
        findings=findings,
    )

    # Return structured response
    return RunOut(
        id=run.id,
        upload_id=run.upload_id,
        mapping_id=run.mapping_id,
        ruleset_version=run.ruleset_version,
        findings=[Finding(**f) for f in findings],
        counts={
            "total": len(rows) + len(invalid_rows),
            "valid": len(rows),
            "invalid": len(invalid_rows),
        },
        invalid_rows=invalid_rows[:50],
        risk_points=bundle["risk_points"],
        compliance_score=bundle["compliance_score"],
        severity_summary=severity_summary,  # safety cap
    )


@router.get("/{run_id}/report.pdf")
def get_report(
    run_id: int,
    user=Depends(require_role("admin", "auditor", "viewer")),
):
    try:
        path = report_path_for_run(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path=path, filename=f"run_{run_id}.pdf")
