from __future__ import annotations
import pandas as pd
from typing import Dict, List, Tuple
from pydantic import ValidationError

from core.normalize.schema import CanonicalPayrollRow
from core.utils.date import safe_parse_date  # adjust if your path differs

CANON_FIELDS = list(CanonicalPayrollRow.model_fields.keys())


def normalize(
    df: pd.DataFrame,
    mapping: Dict[str, str]
) -> Tuple[List[CanonicalPayrollRow], List[dict]]:

    missing = [f for f in ["employee_id", "gross_pay", "net_pay"] if f not in mapping]
    if missing:
        raise ValueError(f"Missing required mappings: {missing}")

    # Ensure mapped columns exist
    for canon, col in mapping.items():
        if col not in df.columns:
            raise ValueError(f"Mapped column not found in file: {canon} -> {col}")

    valid_rows: List[CanonicalPayrollRow] = []
    invalid_rows: List[dict] = []

    for idx, r in df.iterrows():
        data = {}

        # Apply mapping
        for canon, col in mapping.items():
            data[canon] = r.get(col)

        # ---- BASIC COERCIONS ----
        try:
            data["employee_id"] = str(data["employee_id"])

            for k in [
                "gross_pay", "net_pay", "paye", "usc",
                "prsi_ee", "prsi_er", "pension_ee", "pension_er"
            ]:
                if k in data and data[k] is not None:
                    data[k] = float(data[k])

            # ---- DATE NORMALIZATION ----
            for date_field in ["pay_date", "period_start", "period_end"]:
                if date_field in data and data[date_field] is not None:
                    data[date_field] = safe_parse_date(data[date_field])

        except ValueError as e:
            invalid_rows.append({
                "row_number": int(idx) + 1,
                "errors": [{"msg": str(e)}]
            })
            continue
        except Exception as e:
            invalid_rows.append({
                "row_number": int(idx) + 1,
                "errors": [{"msg": f"Coercion error: {str(e)}"}]
            })
            continue

        # ---- SAFE MODEL BUILD ----
        try:
            row = CanonicalPayrollRow(**data)
            valid_rows.append(row)
        except ValidationError as e:
            invalid_rows.append({
                "row_number": int(idx) + 1,
                "errors": e.errors(),
            })

    return valid_rows, invalid_rows
