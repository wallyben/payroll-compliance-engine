"""core/services/payroll_review_service.py
------------------------------------------
Single-entry-point orchestrator for the full payroll review pipeline.

Call ``review_payroll(client_id, payroll_rows)`` to execute every stage of the
review in a fixed, deterministic order and receive a single structured result.

Pipeline order
--------------
 1.  Retrieve previous payroll run       get_previous_run()
 2.  Accept normalised rows              (CanonicalPayrollRow inputs)
 3.  Run compliance rules                run_all()
 4.  Run anomaly detection               run_anomaly_checks()
 5.  Run pre-submission QA checks        run_pre_submission_checks()
 6.  Run payroll diff                    compare_payrolls()
 7.  Compute financial exposure          quantify_exposure()
 8.  Compute audit risk score            score_bundle()  →  audit_risk
 9.  Generate review decision            _make_review_decision()
10.  Generate certificate                generate_certificate()
11.  Generate bureau summary             generate_bureau_summary()
12.  Generate evidence pack              build_evidence_pack()
13.  Persist payroll run                 create_payroll_run()

Design constraints
------------------
- Fully deterministic: identical inputs always produce identical stable outputs.
- No side effects outside the client context (only the client's own run store is
  mutated; no global state is touched).
- Existing module interfaces are preserved without modification.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Dict, List, Optional

from core.analysis.payroll_diff import compare_payrolls
from core.domain.payroll_run import PayrollRun, create_payroll_run, get_previous_run
from core.normalize.schema import CanonicalPayrollRow
from core.reporting.bureau_summary import generate_bureau_summary
from core.reporting.certificate import generate_certificate
from core.reporting.evidence_pack import build_evidence_pack
from core.reporting.exposure_engine import quantify_exposure
from core.review.pre_submission_checks import run_pre_submission_checks
from core.rules.anomaly_rules import run_anomaly_checks
from core.rules.engine import load_ie_config, run_all
from core.scoring.risk import score_bundle

# Semantic version of the compliance engine embedded in every certificate.
_ENGINE_VERSION = "1.0.0"

# Severity labels that block payroll submission.
_BLOCKING_SEVERITIES: frozenset[str] = frozenset({"HIGH", "CRITICAL"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def review_payroll(
    client_id: str,
    payroll_rows: List[CanonicalPayrollRow],
    *,
    scan_date: str = "",
) -> Dict[str, Any]:
    """Execute the full payroll review pipeline for *client_id*.

    Parameters
    ----------
    client_id:
        Identifier of the payroll bureau client.  Used to retrieve the
        previous run and to persist the current run.

    payroll_rows:
        Normalised payroll rows for the period being reviewed.  Rows must
        already be validated ``CanonicalPayrollRow`` instances — ingestion
        and normalization are the caller's responsibility.

    scan_date:
        ISO-8601 date string embedded in the compliance certificate.  Pass
        explicitly for deterministic certificates (e.g. in tests pass "").
        Defaults to empty string so the certificate is always reproducible.

    Returns
    -------
    {
        "review_decision": dict    status / violation / warning counts
        "findings":        list    compliance violations (run_all)
        "anomalies":       list    anomaly detections (run_anomaly_checks)
        "qa_checks":       list    pre-submission QA findings
        "payroll_diff":    dict    employee-level changes vs previous run
        "exposure":        dict    quantified financial exposure
        "audit_risk":      dict    risk points, compliance score, risk band
        "certificate":     dict    deterministic compliance certificate
        "bureau_summary":  dict    one-page bureau-facing summary
        "evidence_pack":   dict    full audit-ready evidence package
    }
    """
    # ── Step 1: Retrieve previous run ────────────────────────────────────────
    previous_run: Optional[PayrollRun] = get_previous_run(client_id)
    previous_rows: List[CanonicalPayrollRow] = (
        previous_run.normalized_rows if previous_run else []
    )

    # ── Step 2: Current rows (already normalised by caller) ──────────────────
    current_rows: List[CanonicalPayrollRow] = payroll_rows

    # ── Step 3: Compliance rules ──────────────────────────────────────────────
    ie_config = load_ie_config()
    findings: List[dict] = run_all(current_rows, ie_config)

    # ── Step 4: Anomaly detection ─────────────────────────────────────────────
    anomalies: List[dict] = run_anomaly_checks(current_rows, previous_rows)

    # ── Step 5: Pre-submission QA ─────────────────────────────────────────────
    qa_checks: List[dict] = run_pre_submission_checks(previous_rows, current_rows)

    # ── Step 6: Payroll diff ──────────────────────────────────────────────────
    payroll_diff: Dict[str, Any] = compare_payrolls(previous_rows, current_rows)

    # ── Combined findings for scoring and certificate ─────────────────────────
    # Compliance violations + anomaly detections are scored together.
    # QA checks are surfaced in the output but excluded from the risk score so
    # that informational QA warnings do not inflate the statutory risk figure.
    all_findings: List[dict] = findings + anomalies

    # ── Step 7: Financial exposure ────────────────────────────────────────────
    exposure: Dict[str, Any] = quantify_exposure(all_findings)

    # ── Step 8: Audit risk score ──────────────────────────────────────────────
    audit_risk: Dict[str, Any] = score_bundle(all_findings)

    # ── Step 9: Review decision ───────────────────────────────────────────────
    review_decision: Dict[str, Any] = _make_review_decision(
        findings, anomalies, qa_checks
    )

    # ── Build run_out for the reporting layer ─────────────────────────────────
    findings_hash = _compute_findings_hash(all_findings)
    dataset_hash = _compute_dataset_hash(current_rows)
    run_out: Dict[str, Any] = {
        "findings": all_findings,
        "findings_hash": findings_hash,
        "ruleset_version": ie_config.get("ruleset_version", ""),
        "compliance_score": audit_risk["compliance_score"],
    }

    # ── Step 10: Certificate ──────────────────────────────────────────────────
    certificate: Dict[str, Any] = generate_certificate(
        run_out, _ENGINE_VERSION, scan_date=scan_date or None
    )

    # ── Step 11: Bureau summary ───────────────────────────────────────────────
    bureau_summary: Dict[str, Any] = generate_bureau_summary(
        run_out, exposure, certificate, len(current_rows)
    )

    # ── Step 12: Evidence pack ────────────────────────────────────────────────
    evidence_pack: Dict[str, Any] = build_evidence_pack(
        run_out, exposure, certificate, bureau_summary, dataset_hash
    )

    # ── Step 13: Persist run ──────────────────────────────────────────────────
    period_start, period_end = _derive_period(current_rows)
    create_payroll_run(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        dataset_hash=dataset_hash,
        normalized_rows=current_rows,
        risk_score=float(audit_risk["risk_points"]),
        findings=all_findings,
    )

    return {
        "review_decision": review_decision,
        "findings": findings,
        "anomalies": anomalies,
        "qa_checks": qa_checks,
        "payroll_diff": payroll_diff,
        "exposure": exposure,
        "audit_risk": audit_risk,
        "certificate": certificate,
        "bureau_summary": bureau_summary,
        "evidence_pack": evidence_pack,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_review_decision(
    findings: List[dict],
    anomalies: List[dict],
    qa_checks: List[dict],
) -> Dict[str, Any]:
    """Derive a submission decision from findings across all three check layers.

    Status rules (evaluated in order):
      REJECTED        – any HIGH / CRITICAL finding in compliance or QA layer
      REQUIRES_REVIEW – any anomaly detected OR any MEDIUM-severity finding
      APPROVED        – no findings of any kind across all layers
    """
    all_items = findings + anomalies + qa_checks
    high_critical_count = sum(
        1 for f in all_items
        if (f.get("severity") or "").upper() in _BLOCKING_SEVERITIES
    )
    medium_count = sum(
        1 for f in all_items
        if (f.get("severity") or "").upper() == "MEDIUM"
    )

    if high_critical_count > 0:
        status = "REJECTED"
    elif anomalies or medium_count > 0:
        status = "REQUIRES_REVIEW"
    else:
        status = "APPROVED"

    return {
        "status": status,
        "violations": high_critical_count,
        "warnings": medium_count,
        "anomalies_detected": len(anomalies),
        "qa_issues": len(qa_checks),
    }


def _compute_findings_hash(findings: List[dict]) -> str:
    """SHA-256 of the serialised findings list (rule-engine order preserved)."""
    serialized = json.dumps(findings, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _compute_dataset_hash(rows: List[CanonicalPayrollRow]) -> str:
    """SHA-256 of the sorted, serialised canonical payroll rows.

    Rows are sorted by ``employee_id`` before serialisation so that the hash
    is stable regardless of the order in which rows were supplied.
    """
    sorted_rows = sorted(rows, key=lambda r: r.employee_id)
    payload = json.dumps(
        [r.model_dump(mode="json") for r in sorted_rows],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _derive_period(rows: List[CanonicalPayrollRow]) -> tuple[date, date]:
    """Derive (period_start, period_end) from the rows' date fields.

    Inspects ``period_start``, ``period_end``, and ``pay_date`` on every row.
    Falls back to ``date.today()`` when no date fields are populated.
    """
    all_dates = [
        d
        for r in rows
        for d in (r.period_start, r.period_end, r.pay_date)
        if d is not None
    ]
    if all_dates:
        return min(all_dates), max(all_dates)
    today = date.today()
    return today, today
