# core/rules/validators.py

from typing import Iterable
from decimal import Decimal, ROUND_HALF_UP

def money_round(value: float | Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def is_non_negative(value: float | Decimal) -> bool:
    return money_round(value) >= Decimal("0.00")

def in_allow_list(value: str, allowed: Iterable[str]) -> bool:
    return value in allowed

def require_fields(row, fields: Iterable[str]) -> bool:
    for field in fields:
        if not hasattr(row, field):
            return False
        if getattr(row, field) is None:
            return False
    return True
