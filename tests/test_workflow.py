"""tests/test_workflow.py
Tests for product/workflow/payroll_workflow.py

Covers:
- State transition: APPROVED → SAFE_TO_SUBMIT
- State transition: REQUIRES_REVIEW → REVIEW_REQUIRED
- State transition: REJECTED → REVIEW_REQUIRED
- Unknown engine status defaults to REVIEW_REQUIRED
- Workflow state stored and retrieved per run_id
- Multi-client isolation
- mark_submitted transitions SAFE_TO_SUBMIT → SUBMITTED
- mark_submitted is a no-op for non-SAFE_TO_SUBMIT states
- get_workflow_state returns None for unknown run_id
- Deterministic: same input → same state
"""
from __future__ import annotations

import pytest

from product.workflow.payroll_workflow import (
    WorkflowState,
    _clear_workflow_store,
    get_client_workflow_history,
    get_workflow_state,
    mark_submitted,
    update_workflow_state,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_stores():
    """Isolate each test by clearing the workflow store."""
    _clear_workflow_store()
    yield
    _clear_workflow_store()


def _run_result(status: str) -> dict:
    """Build a minimal run_result with the given review_decision status."""
    return {"review_decision": {"status": status}}


# ---------------------------------------------------------------------------
# State transition tests
# ---------------------------------------------------------------------------

def test_approved_maps_to_safe_to_submit():
    record = update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    assert record.state == WorkflowState.SAFE_TO_SUBMIT


def test_requires_review_maps_to_review_required():
    record = update_workflow_state(_run_result("REQUIRES_REVIEW"), run_id="run-1", client_id="c1")
    assert record.state == WorkflowState.REVIEW_REQUIRED


def test_rejected_maps_to_review_required():
    record = update_workflow_state(_run_result("REJECTED"), run_id="run-1", client_id="c1")
    assert record.state == WorkflowState.REVIEW_REQUIRED


def test_unknown_engine_status_defaults_to_review_required():
    record = update_workflow_state(_run_result("SOME_FUTURE_STATUS"), run_id="run-1", client_id="c1")
    assert record.state == WorkflowState.REVIEW_REQUIRED


def test_empty_review_decision_defaults_to_review_required():
    record = update_workflow_state({}, run_id="run-1", client_id="c1")
    assert record.state == WorkflowState.REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

def test_get_workflow_state_returns_stored_record():
    update_workflow_state(_run_result("APPROVED"), run_id="run-abc", client_id="c1")
    record = get_workflow_state("run-abc")
    assert record is not None
    assert record.run_id == "run-abc"
    assert record.state == WorkflowState.SAFE_TO_SUBMIT


def test_get_workflow_state_returns_none_for_unknown_run_id():
    assert get_workflow_state("does-not-exist") is None


def test_review_status_raw_value_stored():
    record = update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    assert record.review_status == "APPROVED"


def test_client_id_stored_in_record():
    record = update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="CLIENT-X")
    assert record.client_id == "CLIENT-X"


# ---------------------------------------------------------------------------
# Multi-run / multi-client isolation
# ---------------------------------------------------------------------------

def test_separate_run_ids_have_independent_states():
    update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    update_workflow_state(_run_result("REJECTED"), run_id="run-2", client_id="c1")

    assert get_workflow_state("run-1").state == WorkflowState.SAFE_TO_SUBMIT
    assert get_workflow_state("run-2").state == WorkflowState.REVIEW_REQUIRED


def test_multi_client_isolation():
    update_workflow_state(_run_result("APPROVED"), run_id="run-a", client_id="client-A")
    update_workflow_state(_run_result("REJECTED"), run_id="run-b", client_id="client-B")

    history_a = get_client_workflow_history("client-A")
    history_b = get_client_workflow_history("client-B")

    assert len(history_a) == 1
    assert len(history_b) == 1
    assert history_a[0].state == WorkflowState.SAFE_TO_SUBMIT
    assert history_b[0].state == WorkflowState.REVIEW_REQUIRED


def test_get_client_workflow_history_ordered_by_created_at():
    update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    update_workflow_state(_run_result("REJECTED"), run_id="run-2", client_id="c1")
    update_workflow_state(_run_result("REQUIRES_REVIEW"), run_id="run-3", client_id="c1")

    history = get_client_workflow_history("c1")
    assert len(history) == 3
    # created_at should be non-decreasing (ordered ascending).
    timestamps = [r.created_at for r in history]
    assert timestamps == sorted(timestamps)


def test_get_client_workflow_history_empty_for_unknown_client():
    assert get_client_workflow_history("unknown-client") == []


# ---------------------------------------------------------------------------
# mark_submitted
# ---------------------------------------------------------------------------

def test_mark_submitted_transitions_safe_to_submitted():
    update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    record = mark_submitted("run-1")
    assert record is not None
    assert record.state == WorkflowState.SUBMITTED


def test_mark_submitted_is_noop_for_review_required():
    update_workflow_state(_run_result("REJECTED"), run_id="run-1", client_id="c1")
    record = mark_submitted("run-1")
    assert record is not None
    assert record.state == WorkflowState.REVIEW_REQUIRED  # unchanged


def test_mark_submitted_returns_none_for_unknown_run_id():
    result = mark_submitted("nonexistent-run")
    assert result is None


def test_mark_submitted_persists_in_store():
    update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    mark_submitted("run-1")
    record = get_workflow_state("run-1")
    assert record.state == WorkflowState.SUBMITTED


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_deterministic_same_status_same_state():
    """Calling update_workflow_state twice with identical status yields the same state."""
    result_a = update_workflow_state(_run_result("APPROVED"), run_id="run-a", client_id="c1")
    _clear_workflow_store()
    result_b = update_workflow_state(_run_result("APPROVED"), run_id="run-a", client_id="c1")
    assert result_a.state == result_b.state
    assert result_a.review_status == result_b.review_status


def test_overwrite_run_id_replaces_record():
    """A second call with the same run_id updates the stored record."""
    update_workflow_state(_run_result("APPROVED"), run_id="run-1", client_id="c1")
    update_workflow_state(_run_result("REJECTED"), run_id="run-1", client_id="c1")
    record = get_workflow_state("run-1")
    assert record.state == WorkflowState.REVIEW_REQUIRED
