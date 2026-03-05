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
    total_deductions: Optional[float] = None  # optional; can be derived from paye+usc+prsi_ee+pension_ee
    prsi_class: Optional[str] = None
    weekly_earnings: Optional[float] = None
    age: Optional[int] = None
    bik_value: Optional[float] = None
    allowance_type: Optional[str] = None
    job_title: Optional[str] = None
    pay_period: Optional[str] = None
