from __future__ import annotations

import math
from datetime import date
from typing import Optional

from pydantic import BaseModel, field_validator


class CanonicalPayrollRow(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    ppsn: Optional[str] = None  # encrypted at rest if persisted
    pay_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None

    gross_pay: float
    net_pay: float

    paye: float = 0.0
    usc: float = 0.0
    prsi_ee: float = 0.0
    prsi_er: float = 0.0
    prsi_class: Optional[str] = None  # e.g. "A", "B", "S" — validated by rules layer

    pension_ee: float = 0.0
    pension_er: float = 0.0

    hours: Optional[float] = None
    hourly_rate: Optional[float] = None  # reported rate from source; rules layer validates

    # ------------------------------------------------------------------
    # Field-level guards — enforce the ingestion contract without
    # auto-correcting or inferring any value.
    # ------------------------------------------------------------------

    @field_validator("employee_id", mode="after")
    @classmethod
    def _reject_empty_employee_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("employee_id must not be empty or whitespace-only")
        return v

    @field_validator(
        "gross_pay", "net_pay",
        "paye", "usc",
        "prsi_ee", "prsi_er",
        "pension_ee", "pension_er",
        "hours", "hourly_rate",
        mode="after",
    )
    @classmethod
    def _reject_nan_inf(cls, v: float | None) -> float | None:
        """NaN and Infinity are not valid payroll values at the schema boundary."""
        if v is not None and (math.isnan(v) or math.isinf(v)):
            raise ValueError(
                "numeric field must be a finite number (NaN and Infinity are not accepted)"
            )
        return v
