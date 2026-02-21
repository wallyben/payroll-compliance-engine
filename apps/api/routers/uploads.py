from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
from apps.api.db import get_db
from apps.api import models
from apps.api.schemas import UploadOut
from apps.api.deps import require_role

router = APIRouter()
STORE = Path("storage/uploads")
STORE.mkdir(parents=True, exist_ok=True)

@router.post("", response_model=UploadOut)
def upload_file(
    f: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_role("admin","auditor"))
):
    if not f.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    suffix = Path(f.filename).suffix.lower()
    if suffix not in {".csv",".xlsx",".xls"}:
        raise HTTPException(status_code=400, detail="Unsupported file type (CSV/XLSX only)")
    dest = STORE / f"{abs(hash(f.filename))}_{f.filename}"
    with dest.open("wb") as out:
        shutil.copyfileobj(f.file, out)
    u = models.Upload(filename=f.filename, content_type=f.content_type or "", stored_path=str(dest))
    db.add(u); db.commit(); db.refresh(u)
    return UploadOut(id=u.id, filename=u.filename)
