from __future__ import annotations

from pathlib import Path

import pandas as pd

ALLOWED_EXTS = {".csv", ".xlsx", ".xls"}

# Columns that must be present for any payroll file to be processable.
REQUIRED_COLUMNS = {"employee_id", "gross_pay", "net_pay"}

# Encoding probe order: BOM-aware UTF-8 first, then plain UTF-8, then latin-1 fallback.
_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


def load_table(path: str) -> pd.DataFrame:
    """Load a payroll file into a DataFrame.

    Guarantees:
    - Only files with supported extensions are accepted.
    - Required columns must be present; missing columns raise ValueError.
    - Files with no data rows (header-only) are rejected.
    - All cell values are returned as raw strings so the normalisation layer
      performs all type coercion explicitly with no silent pandas inference.
    - Column names are stripped of surrounding whitespace for consistency.
    - The returned DataFrame is a copy; callers cannot inadvertently mutate
      the loaded data by reference.
    """
    p = Path(path)
    if p.suffix.lower() not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported file type: {p.suffix}")
    if p.suffix.lower() == ".csv":
        df = _load_csv(p)
    else:
        df = _load_excel(p)
    _validate_structure(df, p)
    return df.copy()


def _load_csv(p: Path) -> pd.DataFrame:
    """Read a CSV with encoding fallback and raw string dtypes.

    dtype=str prevents pandas from silently coercing numeric or date columns.
    keep_default_na=False prevents pandas from converting empty strings and
    sentinel values ("NA", "NULL", etc.) to NaN before the caller sees them.
    """
    for encoding in _ENCODINGS:
        try:
            df = pd.read_csv(p, dtype=str, encoding=encoding, keep_default_na=False)
            df.columns = [c.strip() for c in df.columns]
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode '{p.name}': tried encodings {_ENCODINGS}")


def _load_excel(p: Path) -> pd.DataFrame:
    """Read an Excel file with raw string dtypes and structured error wrapping."""
    try:
        df = pd.read_excel(p, dtype=str)
    except Exception as exc:
        raise ValueError(f"Cannot read Excel file '{p.name}': {exc}") from exc
    df.columns = [c.strip() for c in df.columns]
    return df


def _validate_structure(df: pd.DataFrame, p: Path) -> None:
    """Raise ValueError for files that are structurally unusable."""
    present = {c.lower() for c in df.columns}
    missing = {c for c in REQUIRED_COLUMNS if c not in present}
    if missing:
        raise ValueError(
            f"Missing required columns in '{p.name}': {sorted(missing)}"
        )
    if len(df) == 0:
        raise ValueError(f"File '{p.name}' contains no data rows.")
