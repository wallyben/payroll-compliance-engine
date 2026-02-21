from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from pathlib import Path

from apps.api.db import get_db
from apps.api import models
from apps.api.schemas import RunOut, Finding
from apps.api.deps import require_role
from apps.api.settings import settings

from core.ingest.loader import load_table
from core.normalize.mapper import normalize
from core.rules.engine import run_all
from core.scoring.risk import score_bundle
from core.reporting.pdf import build_pdf

router = APIRouter()
CFG_PATH = Path("core/rules/ie_config_2026.json")


def _load_cfg():
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


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

    cfg = _load_cfg()

    # Load file
    df = load_table(upload.stored_path)

    # Apply mapping + normalization
    mapping_dict = json.loads(mapping.mapping_json)
    rows, invalid_rows = normalize(df, mapping_dict)

    # Run rules only on valid rows
    findings = run_all(rows, cfg)
    bundle = score_bundle(findings)

    # Phase 3 — Deterministic severity summary
    severity_summary = {
        "HIGH": sum(1 for f in findings if f["severity"] == "HIGH"),
        "MEDIUM": sum(1 for f in findings if f["severity"] == "MEDIUM"),
        "LOW": sum(1 for f in findings if f["severity"] == "LOW"),
        "TOTAL": len(findings),
    }
    

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
    pdf_dir = Path("storage/reports")
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"run_{run.id}.pdf"

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
    path = Path("storage/reports") / f"run_{run_id}.pdf"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    # v1: returning path (in production you'd stream file)
    return {"path": str(path.resolve())}
