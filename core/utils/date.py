from datetime import date, timedelta
from typing import Any, Optional

from dateutil import parser


def safe_parse_date(value: Any) -> Optional[date]:
    if value in (None, "", " "):
        return None

    if isinstance(value, date):
        return value

    # Excel serial numbers (reasonable modern range)
    if isinstance(value, (int, float)) and 20000 <= value <= 90000:
        base = date(1899, 12, 30)
        return base + timedelta(days=int(value))

    try:
        dt = parser.parse(str(value), dayfirst=True)
        return dt.date()
    except Exception:
        raise ValueError(f"Invalid date format: {value}")
