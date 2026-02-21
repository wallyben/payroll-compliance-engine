from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from apps.api.db import get_db
from apps.api import models
from apps.api.schemas import MappingIn, MappingOut
from apps.api.deps import require_role
from core.normalize.schema import CanonicalPayrollRow

router = APIRouter()

@router.post("/{upload_id}", response_model=MappingOut)
def set_mapping(upload_id: int, body: MappingIn, db: Session = Depends(get_db), user=Depends(require_role("admin","auditor"))):
    upload = db.query(models.Upload).get(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Guardrail: mapping keys must be canonical schema fields
    allowed = set(CanonicalPayrollRow.model_fields.keys())
    for k in body.mapping.keys():
        if k not in allowed:
            raise HTTPException(status_code=400, detail=f"Unknown canonical field: {k}")

    m = models.Mapping(upload_id=upload_id, mapping_json=json.dumps(body.mapping))
    db.add(m); db.commit(); db.refresh(m)
    return MappingOut(id=m.id, upload_id=m.upload_id, mapping=body.mapping)
