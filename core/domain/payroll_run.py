from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

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
    # Risk enrichment — populated after rules engine execution.
    # risk_score: raw risk-points total (higher = more risk).
    risk_score: float = 0.0
    findings: List[Dict[str, Any]] = []


def create_payroll_run(
    client_id: str,
    period_start: date,
    period_end: date,
    dataset_hash: str,
    normalized_rows: List[CanonicalPayrollRow],
    *,
    risk_score: float = 0.0,
    findings: List[Dict[str, Any]] | None = None,
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
        risk_score=risk_score,
        findings=findings if findings is not None else [],
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


def get_client_runs(client_id: str) -> List["PayrollRun"]:
    """Return all payroll runs for *client_id*, ordered by period_end then created_at."""
    return sorted(
        [r for r in _run_store if r.client_id == client_id],
        key=lambda r: (r.period_end, r.created_at),
    )


def _clear_runs() -> None:
    """Reset the run store — for testing only."""
    _run_store.clear()
