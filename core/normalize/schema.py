from pydantic import BaseModel
from typing import Optional
from datetime import date

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

    pension_ee: float = 0.0
    pension_er: float = 0.0

    hours: Optional[float] = None
