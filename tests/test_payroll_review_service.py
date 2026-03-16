"""tests/test_payroll_review_service.py
---------------------------------------
Integration tests for core/services/payroll_review_service.py.

Each test class is isolated via the ``clear_stores`` autouse fixture so that
run-store state does not leak between tests.

Test design philosophy
----------------------
These tests exercise the SERVICE ORCHESTRATION layer — that every pipeline
stage is called and its output is wired to the right downstream stage — not
the internal correctness of individual rule engines (those are covered by
their own unit tests).

Row construction
----------------
Rows that trigger specific behaviours (violations, anomalies) are built with
deliberate "bad" values.  "Neutral" rows avoid easily-triggered HIGH
violations but may still produce LOW/MEDIUM findings from the rule engine;
tests that care about finding counts use explicit fixture rows.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List

import pytest

from core.domain.payroll_run import _clear_runs, get_previous_run
from core.normalize.schema import CanonicalPayrollRow
from core.services.payroll_review_service import review_payroll

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

_SCAN_DATE = ""          # empty → deterministic certificate
_PERIOD_START = date(2024, 1, 1)
_PERIOD_END   = date(2024, 1, 31)

_REQUIRED_OUTPUT_KEYS = frozenset({
    "review_decision",
    "findings",
    "anomalies",
    "qa_checks",
    "payroll_diff",
    "exposure",
    "audit_risk",
    "certificate",
    "bureau_summary",
    "evidence_pack",
})

_REQUIRED_DECISION_KEYS = frozenset({
    "status", "violations", "warnings", "anomalies_detected", "qa_issues"
})

_VALID_STATUSES = frozenset({"APPROVED", "REQUIRES_REVIEW", "REJECTED"})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_stores():
    _clear_runs()
    yield
    _clear_runs()


def _row(
    employee_id: str,
    gross_pay: float = 3000.0,
    *,
    net_pay: float | None = None,
    paye: float = 0.0,
    usc: float = 0.0,
    prsi_ee: float = 0.0,
    prsi_er: float = 0.0,
    hours: float | None = None,
    period_start: date = _PERIOD_START,
    period_end: date = _PERIOD_END,
    ppsn: str | None = None,
    prsi_class: str | None = None,
) -> CanonicalPayrollRow:
    """Build a CanonicalPayrollRow with sensible defaults."""
    _net = net_pay if net_pay is not None else gross_pay - paye - usc - prsi_ee
    return CanonicalPayrollRow(
        employee_id=employee_id,
        gross_pay=gross_pay,
        net_pay=_net,
        paye=paye,
        usc=usc,
        prsi_ee=prsi_ee,
        prsi_er=prsi_er,
        hours=hours,
        period_start=period_start,
        period_end=period_end,
        ppsn=ppsn,
        prsi_class=prsi_class,
    )


def _violation_row(employee_id: str) -> CanonicalPayrollRow:
    """Row with negative PAYE — guaranteed HIGH finding (rule_paye_004_negative)."""
    return _row(employee_id, gross_pay=3000.0, paye=-200.0, net_pay=3200.0)


def _anomaly_row_current(employee_id: str, prev_gross: float) -> CanonicalPayrollRow:
    """Gross pay 3× previous — exceeds 50 % anomaly threshold."""
    return _row(employee_id, gross_pay=prev_gross * 3.0)


# ---------------------------------------------------------------------------
# Test: clean payroll run
# ---------------------------------------------------------------------------


class TestCleanPayrollRun:
    """Verify that a structurally sound payroll produces the correct output shape."""

    def _run(self) -> dict:
        rows = [
            _row("E001", 3000.0, paye=600.0, usc=60.0, prsi_ee=90.0),
            _row("E002", 2500.0, paye=500.0, usc=50.0, prsi_ee=75.0),
        ]
        return review_payroll("CLEAN_CLIENT", rows, scan_date=_SCAN_DATE)

    def test_output_has_all_required_keys(self):
        result = self._run()
        assert set(result.keys()) == _REQUIRED_OUTPUT_KEYS

    def test_review_decision_has_required_keys(self):
        result = self._run()
        assert set(result["review_decision"].keys()) == _REQUIRED_DECISION_KEYS

    def test_review_decision_status_is_valid(self):
        result = self._run()
        assert result["review_decision"]["status"] in _VALID_STATUSES

    def test_findings_and_anomalies_are_lists(self):
        result = self._run()
        assert isinstance(result["findings"], list)
        assert isinstance(result["anomalies"], list)
        assert isinstance(result["qa_checks"], list)

    def test_payroll_diff_has_expected_keys(self):
        result = self._run()
        diff = result["payroll_diff"]
        assert "new_employees" in diff
        assert "removed_employees" in diff
        assert "payroll_total_change" in diff

    def test_exposure_has_expected_keys(self):
        result = self._run()
        exp = result["exposure"]
        assert "exposure_total" in exp
        assert "employees_impacted" in exp
        assert "exposure_by_rule" in exp

    def test_audit_risk_has_expected_keys(self):
        result = self._run()
        ar = result["audit_risk"]
        assert "risk_points" in ar
        assert "compliance_score" in ar
        assert "risk_band" in ar

    def test_certificate_has_expected_keys(self):
        result = self._run()
        cert = result["certificate"]
        assert "certificate_id" in cert
        assert "validation_status" in cert
        assert "violations_found" in cert
        assert "rules_checked" in cert

    def test_bureau_summary_has_expected_keys(self):
        result = self._run()
        bs = result["bureau_summary"]
        assert "validation_status" in bs
        assert "risk_score" in bs
        assert "confidence" in bs
        assert "employees_scanned" in bs

    def test_employees_scanned_matches_row_count(self):
        result = self._run()
        assert result["bureau_summary"]["employees_scanned"] == 2

    def test_evidence_pack_has_expected_keys(self):
        result = self._run()
        ep = result["evidence_pack"]
        assert "scan_metadata" in ep
        assert "validation_summary" in ep
        assert "exposure_analysis" in ep
        assert "certificate" in ep
        assert "bureau_summary" in ep
        assert "findings" in ep

    def test_run_is_persisted_for_client(self):
        self._run()
        run = get_previous_run("CLEAN_CLIENT")
        assert run is not None
        assert run.client_id == "CLEAN_CLIENT"

    def test_run_stores_risk_score(self):
        result = self._run()
        run = get_previous_run("CLEAN_CLIENT")
        assert run.risk_score == float(result["audit_risk"]["risk_points"])

    def test_run_stores_findings(self):
        result = self._run()
        run = get_previous_run("CLEAN_CLIENT")
        expected = result["findings"] + result["anomalies"]
        assert run.findings == expected

    def test_first_run_has_empty_previous_rows(self):
        result = self._run()
        # No previous run → all employees are "new" in the diff
        assert result["payroll_diff"]["removed_employees"] == []

    def test_no_anomalies_on_first_run(self):
        """Anomaly rules require a previous run to compare against."""
        result = self._run()
        assert result["anomalies"] == []


# ---------------------------------------------------------------------------
# Test: payroll with compliance violations
# ---------------------------------------------------------------------------


class TestPayrollWithComplianceViolations:
    """Confirm that HIGH findings trigger REJECTED and are propagated correctly."""

    def _run(self) -> dict:
        rows = [_violation_row("E001")]
        return review_payroll("VIOLATION_CLIENT", rows, scan_date=_SCAN_DATE)

    def test_high_finding_present(self):
        result = self._run()
        high = [f for f in result["findings"] if f.get("severity") == "HIGH"]
        assert len(high) > 0, "Expected at least one HIGH finding from violation row"

    def test_review_status_is_rejected(self):
        result = self._run()
        assert result["review_decision"]["status"] == "REJECTED"

    def test_violations_count_matches_high_findings(self):
        result = self._run()
        high_count = len([f for f in result["findings"] if f.get("severity") == "HIGH"])
        # violations counts HIGH/CRITICAL across findings + anomalies + qa_checks
        assert result["review_decision"]["violations"] >= high_count

    def test_certificate_status_is_failed(self):
        result = self._run()
        assert result["certificate"]["validation_status"] == "FAILED"

    def test_bureau_summary_status_is_failed(self):
        result = self._run()
        assert result["bureau_summary"]["validation_status"] == "FAILED"

    def test_bureau_summary_confidence_is_low(self):
        result = self._run()
        assert result["bureau_summary"]["confidence"] == "LOW"

    def test_violations_found_in_certificate(self):
        result = self._run()
        assert result["certificate"]["violations_found"] > 0

    def test_evidence_pack_findings_non_empty(self):
        result = self._run()
        assert len(result["evidence_pack"]["findings"]) > 0

    def test_run_persisted_with_non_zero_risk_score(self):
        self._run()
        run = get_previous_run("VIOLATION_CLIENT")
        assert run.risk_score > 0.0


# ---------------------------------------------------------------------------
# Test: payroll with anomalies
# ---------------------------------------------------------------------------


class TestPayrollWithAnomalies:
    """Confirm anomaly detection fires when gross pay increases > 50 % vs prior run."""

    def test_anomaly_detected_on_salary_spike(self):
        prev_rows = [_row("E001", 3000.0)]
        curr_rows = [_anomaly_row_current("E001", 3000.0)]   # 3× prev → +200 %

        # First call: establishes previous run
        review_payroll("ANOMALY_CLIENT", prev_rows, scan_date=_SCAN_DATE)
        # Second call: compares against first run
        result = review_payroll("ANOMALY_CLIENT", curr_rows, scan_date=_SCAN_DATE)

        anomaly_ids = [a["rule_id"] for a in result["anomalies"]]
        assert "IE.ANOMALY.001" in anomaly_ids

    def test_anomaly_triggers_requires_review(self):
        prev_rows = [_row("E001", 3000.0)]
        curr_rows = [_anomaly_row_current("E001", 3000.0)]

        review_payroll("ANOMALY_CLIENT2", prev_rows, scan_date=_SCAN_DATE)
        result = review_payroll("ANOMALY_CLIENT2", curr_rows, scan_date=_SCAN_DATE)

        assert result["review_decision"]["status"] in {"REQUIRES_REVIEW", "REJECTED"}
        assert result["review_decision"]["anomalies_detected"] > 0

    def test_anomalies_empty_without_previous_run(self):
        rows = [_row("E001", 9999.0)]  # no previous run to compare against
        result = review_payroll("NO_PREV_CLIENT", rows, scan_date=_SCAN_DATE)
        assert result["anomalies"] == []

    def test_anomalies_list_in_output(self):
        prev_rows = [_row("E001", 1000.0)]
        curr_rows = [_anomaly_row_current("E001", 1000.0)]

        review_payroll("ANOMALY_CLIENT3", prev_rows, scan_date=_SCAN_DATE)
        result = review_payroll("ANOMALY_CLIENT3", curr_rows, scan_date=_SCAN_DATE)

        assert isinstance(result["anomalies"], list)
        assert len(result["anomalies"]) > 0


# ---------------------------------------------------------------------------
# Test: payroll with employee changes
# ---------------------------------------------------------------------------


class TestPayrollWithEmployeeChanges:
    """Confirm the payroll diff correctly captures headcount changes."""

    def _setup(self) -> dict:
        prev_rows = [
            _row("E001", 3000.0),
            _row("E002", 2500.0),
        ]
        curr_rows = [
            _row("E001", 3000.0),   # unchanged
            _row("E003", 2000.0),   # new employee
            # E002 intentionally absent (removed)
        ]
        review_payroll("CHANGES_CLIENT", prev_rows, scan_date=_SCAN_DATE)
        return review_payroll("CHANGES_CLIENT", curr_rows, scan_date=_SCAN_DATE)

    def test_new_employee_detected_in_diff(self):
        result = self._setup()
        new_ids = [e["employee_id"] for e in result["payroll_diff"]["new_employees"]]
        assert "E003" in new_ids

    def test_removed_employee_detected_in_diff(self):
        result = self._setup()
        removed_ids = [e["employee_id"] for e in result["payroll_diff"]["removed_employees"]]
        assert "E002" in removed_ids

    def test_new_employee_appears_in_qa_checks(self):
        result = self._setup()
        qa_rule_ids = [q["rule_id"] for q in result["qa_checks"]]
        assert "QA.POP.001" in qa_rule_ids  # new employee QA check

    def test_removed_employee_appears_in_qa_checks(self):
        result = self._setup()
        qa_rule_ids = [q["rule_id"] for q in result["qa_checks"]]
        assert "QA.POP.002" in qa_rule_ids  # removed employee QA check

    def test_unchanged_employee_not_in_diff_edges(self):
        result = self._setup()
        new_ids = [e["employee_id"] for e in result["payroll_diff"]["new_employees"]]
        removed_ids = [e["employee_id"] for e in result["payroll_diff"]["removed_employees"]]
        assert "E001" not in new_ids
        assert "E001" not in removed_ids

    def test_payroll_total_change_computed(self):
        result = self._setup()
        ptc = result["payroll_diff"]["payroll_total_change"]
        assert "previous_total" in ptc
        assert "current_total" in ptc
        assert "absolute_change" in ptc


# ---------------------------------------------------------------------------
# Test: repeat execution determinism
# ---------------------------------------------------------------------------


class TestRepeatExecutionDeterministic:
    """Same input on separate clients (no previous run) must yield identical stable outputs."""

    def _rows(self) -> List[CanonicalPayrollRow]:
        return [
            _row("E001", 3000.0, paye=600.0, usc=60.0, prsi_ee=90.0),
            _row("E002", 2000.0, paye=400.0, usc=40.0, prsi_ee=60.0),
        ]

    def test_findings_are_identical(self):
        r1 = review_payroll("DET_A", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_B", self._rows(), scan_date=_SCAN_DATE)
        assert r1["findings"] == r2["findings"]

    def test_anomalies_are_identical(self):
        r1 = review_payroll("DET_C", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_D", self._rows(), scan_date=_SCAN_DATE)
        assert r1["anomalies"] == r2["anomalies"]

    def test_qa_checks_are_identical(self):
        r1 = review_payroll("DET_E", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_F", self._rows(), scan_date=_SCAN_DATE)
        assert r1["qa_checks"] == r2["qa_checks"]

    def test_audit_risk_is_identical(self):
        r1 = review_payroll("DET_G", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_H", self._rows(), scan_date=_SCAN_DATE)
        assert r1["audit_risk"] == r2["audit_risk"]

    def test_certificate_id_is_identical(self):
        r1 = review_payroll("DET_I", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_J", self._rows(), scan_date=_SCAN_DATE)
        assert r1["certificate"]["certificate_id"] == r2["certificate"]["certificate_id"]

    def test_review_decision_is_identical(self):
        r1 = review_payroll("DET_K", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_L", self._rows(), scan_date=_SCAN_DATE)
        assert r1["review_decision"] == r2["review_decision"]

    def test_payroll_diff_is_identical(self):
        r1 = review_payroll("DET_M", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_N", self._rows(), scan_date=_SCAN_DATE)
        assert r1["payroll_diff"] == r2["payroll_diff"]

    def test_evidence_pack_scan_metadata_hash_identical(self):
        r1 = review_payroll("DET_O", self._rows(), scan_date=_SCAN_DATE)
        r2 = review_payroll("DET_P", self._rows(), scan_date=_SCAN_DATE)
        assert (
            r1["evidence_pack"]["scan_metadata"]["dataset_hash"]
            == r2["evidence_pack"]["scan_metadata"]["dataset_hash"]
        )
        assert (
            r1["evidence_pack"]["scan_metadata"]["findings_hash"]
            == r2["evidence_pack"]["scan_metadata"]["findings_hash"]
        )

    def test_input_row_order_does_not_affect_dataset_hash(self):
        rows_asc = [
            _row("E001", 3000.0, paye=600.0),
            _row("E002", 2000.0, paye=400.0),
        ]
        rows_desc = [
            _row("E002", 2000.0, paye=400.0),
            _row("E001", 3000.0, paye=600.0),
        ]
        r1 = review_payroll("HASH_A", rows_asc, scan_date=_SCAN_DATE)
        r2 = review_payroll("HASH_B", rows_desc, scan_date=_SCAN_DATE)
        assert (
            r1["evidence_pack"]["scan_metadata"]["dataset_hash"]
            == r2["evidence_pack"]["scan_metadata"]["dataset_hash"]
        )


# ---------------------------------------------------------------------------
# Test: multiple clients isolation
# ---------------------------------------------------------------------------


class TestMultipleClientsIsolation:
    """Confirm that clients share no state and previous-run lookups are scoped."""

    def test_clients_do_not_share_previous_run(self):
        rows_a = [_row("E001", 5000.0)]
        rows_b = [_row("E001", 1000.0)]

        review_payroll("ISO_A", rows_a, scan_date=_SCAN_DATE)
        review_payroll("ISO_B", rows_b, scan_date=_SCAN_DATE)

        run_a = get_previous_run("ISO_A")
        run_b = get_previous_run("ISO_B")
        assert run_a.client_id == "ISO_A"
        assert run_b.client_id == "ISO_B"
        assert run_a.run_id != run_b.run_id

    def test_previous_rows_scoped_per_client(self):
        """Client B's large salary increase should not create anomalies for Client A."""
        prev_a = [_row("E001", 3000.0)]
        prev_b = [_row("E001", 3000.0)]

        review_payroll("ISO_C", prev_a, scan_date=_SCAN_DATE)
        review_payroll("ISO_D", prev_b, scan_date=_SCAN_DATE)

        # Only Client C gets a spike follow-up; Client D's follow-up is clean
        curr_a_spike = [_anomaly_row_current("E001", 3000.0)]
        curr_d_clean = [_row("E001", 3000.0)]  # unchanged

        result_a = review_payroll("ISO_C", curr_a_spike, scan_date=_SCAN_DATE)
        result_d = review_payroll("ISO_D", curr_d_clean, scan_date=_SCAN_DATE)

        assert len(result_a["anomalies"]) > 0, "Client C spike should create anomaly"
        assert result_d["anomalies"] == [], "Client D unchanged run should have no anomalies"

    def test_sequential_runs_build_on_previous(self):
        """Each review_payroll call for the same client adds to that client's history."""
        rows_p1 = [_row("E001", 3000.0, period_end=date(2024, 1, 31))]
        rows_p2 = [_row("E001", 3000.0, period_end=date(2024, 2, 29))]
        rows_p3 = [_row("E001", 3000.0, period_end=date(2024, 3, 31))]

        review_payroll("SEQ_CLIENT", rows_p1, scan_date=_SCAN_DATE)
        review_payroll("SEQ_CLIENT", rows_p2, scan_date=_SCAN_DATE)
        review_payroll("SEQ_CLIENT", rows_p3, scan_date=_SCAN_DATE)

        run = get_previous_run("SEQ_CLIENT")
        assert run is not None
        assert run.period_end == date(2024, 3, 31)

    def test_unknown_client_starts_fresh(self):
        """A client with no prior history receives empty previous rows."""
        result = review_payroll("BRAND_NEW_CLIENT", [_row("E001", 2000.0)], scan_date=_SCAN_DATE)
        # No previous rows → no removed employees, anomalies, or diff salary changes
        assert result["payroll_diff"]["removed_employees"] == []
        assert result["anomalies"] == []
