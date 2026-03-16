"""product/workflow/payroll_workflow.py
--------------------------------------
Tracks the lifecycle of a payroll review run.

Workflow states
---------------
UPLOADED        – payroll file received, not yet reviewed
REVIEWING       – review pipeline in progress
REVIEW_REQUIRED – engine returned REQUIRES_REVIEW or REJECTED
SAFE_TO_SUBMIT  – engine returned APPROVED; ready for submission
SUBMITTED       – payroll has been submitted to the authority

The product layer maps engine review decisions to workflow states; no
compliance or payroll logic is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# State definitions
# ---------------------------------------------------------------------------

class WorkflowState(str, Enum):
    UPLOADED = "UPLOADED"
    REVIEWING = "REVIEWING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SAFE_TO_SUBMIT = "SAFE_TO_SUBMIT"
    SUBMITTED = "SUBMITTED"


# Map engine review_decision.status → product workflow state.
# REJECTED is treated as REVIEW_REQUIRED: specialist review is needed before
# the payroll can proceed.
_ENGINE_STATUS_TO_WORKFLOW: Dict[str, WorkflowState] = {
    "APPROVED": WorkflowState.SAFE_TO_SUBMIT,
    "REQUIRES_REVIEW": WorkflowState.REVIEW_REQUIRED,
    "REJECTED": WorkflowState.REVIEW_REQUIRED,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WorkflowRecord:
    run_id: str
    client_id: str
    state: WorkflowState
    review_status: str      # raw engine status string
    created_at: str         # ISO-8601 UTC timestamp


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_workflow_store: Dict[str, WorkflowRecord] = {}  # keyed by run_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_workflow_state(
    run_result: Dict[str, Any],
    run_id: str,
    client_id: str,
) -> WorkflowRecord:
    """Derive and persist the workflow state from a payroll review result.

    Parameters
    ----------
    run_result:
        The dict returned by ``review_payroll()``.
    run_id:
        Identifier for this payroll run (e.g. PayrollRun.run_id or a UUID).
    client_id:
        Client this run belongs to.

    Returns
    -------
    WorkflowRecord with the resolved state.
    """
    review_decision = run_result.get("review_decision", {})
    engine_status: str = review_decision.get("status", "")
    workflow_state = _ENGINE_STATUS_TO_WORKFLOW.get(
        engine_status, WorkflowState.REVIEW_REQUIRED
    )

    record = WorkflowRecord(
        run_id=run_id,
        client_id=client_id,
        state=workflow_state,
        review_status=engine_status,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _workflow_store[run_id] = record
    return record


def get_workflow_state(run_id: str) -> Optional[WorkflowRecord]:
    """Return the WorkflowRecord for *run_id*, or None if not found."""
    return _workflow_store.get(run_id)


def get_client_workflow_history(client_id: str) -> List[WorkflowRecord]:
    """Return all workflow records for *client_id*, ordered by created_at."""
    records = [r for r in _workflow_store.values() if r.client_id == client_id]
    return sorted(records, key=lambda r: r.created_at)


def mark_submitted(run_id: str) -> Optional[WorkflowRecord]:
    """Transition a SAFE_TO_SUBMIT run to SUBMITTED.

    Only succeeds when the current state is SAFE_TO_SUBMIT.  Returns the
    updated record, or None if *run_id* is unknown.
    """
    record = _workflow_store.get(run_id)
    if record is not None and record.state == WorkflowState.SAFE_TO_SUBMIT:
        record.state = WorkflowState.SUBMITTED
    return record


def _clear_workflow_store() -> None:
    """Reset the workflow store — for testing only."""
    _workflow_store.clear()
