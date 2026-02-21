from __future__ import annotations
from pathlib import Path
import pandas as pd

ALLOWED_EXTS = {".csv", ".xlsx", ".xls"}

def load_table(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported file type: {p.suffix}")
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    return pd.read_excel(p)
