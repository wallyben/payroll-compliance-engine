from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from pydantic import BaseModel

from core.normalize.schema import CanonicalPayrollRow

_run_store: list["PayrollRun"] = []


class PayrollRun(BaseModel):
    run_id: str
    client_id: str
    period_start: date
    period_end: date
    dataset_hash: str
    normalized_rows: List[CanonicalPayrollRow]
    created_at: datetime


def create_payroll_run(
    client_id: str,
    period_start: date,
    period_end: date,
    dataset_hash: str,
    normalized_rows: List[CanonicalPayrollRow],
) -> PayrollRun:
    """Create a payroll run linked to a client and store it."""
    run = PayrollRun(
        run_id=str(uuid.uuid4()),
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        dataset_hash=dataset_hash,
        normalized_rows=normalized_rows,
        created_at=datetime.now(timezone.utc),
    )
    _run_store.append(run)
    return run


def get_previous_run(client_id: str) -> Optional[PayrollRun]:
    """Return the most recent payroll run for *client_id*.

    Runs are ordered by ``period_end`` descending; ``created_at`` is used as a
    tiebreaker so the result is deterministic even when two runs share the same
    period end.  Returns ``None`` when no runs exist for the client.
    """
    client_runs = [r for r in _run_store if r.client_id == client_id]
    if not client_runs:
        return None
    return max(client_runs, key=lambda r: (r.period_end, r.created_at))


def _clear_runs() -> None:
    """Reset the run store — for testing only."""
    _run_store.clear()
