# Payroll Compliance Engine Architecture

This document describes the full pipeline from CSV upload to bureau summary. The engine is **deterministic**, **stateless**, and **CSV-driven**. Same input always produces identical output.

## Pipeline overview

```
CSV upload
  → normalization (mapper)
  → invalid row detection
  → rule execution (row rules, then file rules)
  → findings aggregation + deterministic sort
  → exposure report
  → certificate
  → bureau summary
```

## 1. CSV normalization

- **Module:** `core/normalize/mapper.py`
- **Input:** DataFrame (from CSV) and a mapping from canonical field names to column names.
- **Behaviour:**
  - Required mappings: `employee_id`, `gross_pay`, `net_pay`.
  - Each row is coerced (types, dates) and validated against the canonical schema.
  - Valid rows become `CanonicalPayrollRow` instances; invalid rows are collected with row number and error details.
- **Output:** `(valid_rows: List[CanonicalPayrollRow], invalid_rows: List[dict])`.

## 2. Canonical payroll model

- **Module:** `core/normalize/schema.py`
- **Model:** `CanonicalPayrollRow` (Pydantic).
- **Required fields:** `employee_id`, `gross_pay`, `net_pay`.
- **Optional fields:** employee_name, ppsn, pay_date, period_start, period_end, paye, usc, prsi_ee, prsi_er, pension_ee, pension_er, hours, total_deductions, prsi_class, weekly_earnings, age, bik_value, allowance_type, job_title, pay_period.
- No timestamps or randomness; all values are from the CSV or defaults.

## 3. Rule registry

- **Module:** `core/rules/registry.py`
- **Purpose:** Single source of truth for rule metadata (IE-2026.01).
- **Contents:** 19 rules with `rule_id`, `title`, `severity`, `domain`, `category`, `description`, `remediation`, `exposure_weight`, `ruleset_version`.
- **Severities:** CRITICAL, HIGH, MEDIUM, LOW.
- **Domains:** arithmetic, operational, compliance.
- **Access:** `get_meta(rule_id)`, `all_rule_ids()`.

## 4. Rule execution pipeline

- **Module:** `core/rules/engine.py`
- **Entry point:** `run_all(rows, config, invalid_rows=None)`.
- **Order:**
  1. **IE.DATA.002** (if `invalid_rows` is non-empty): findings for rows with missing critical fields.
  2. **IE-2026.01 row rules** (deterministic order): NET.001, NET.002, DEDUCT.001, PENSION.002, PAY.002, MINWAGE.001, PAY.001, NET.003, PRSI.001, PRSI.004, USC.001, USC.002, AUTOENROL.001, AUTOENROL.002, BIK.001, PRSI.003.
  3. **IE-2026.01 file rules:** TOTALS.001, DATA.001.
  4. **Legacy rules** (unchanged order).
- **Aggregation:** All findings are then sorted deterministically by `(rule_id, first employee_ref)` so that output order is stable.
- **Profile mode:** If `config["scan_profile"]` is set, only rules in the profile’s `active_rules` list run; order is still fixed.

## 5. Exposure engine

- **Module:** `core/reporting/exposure_engine.py`
- **Input:** List of finding dicts (with `rule_id`, `severity`, `amount_impact`, `employee_refs`, optional `category`).
- **Behaviour:**
  - Groups by category (or rule_id).
  - Computes underpayment_total, overpayment_total, employees_impacted, quantifiable / non-quantifiable counts.
  - Uses registry `exposure_weight` for rule_breakdown.
  - Sets confidence_level from proportion of quantifiable findings.
- **Output:** `ExposureReport` (including total_exposure, severity_counts, rule_breakdown). Deterministic; no randomness.

## 6. Certificate builder

- **Module:** `core/reporting/certificate_builder.py`
- **Input:** ExposureReport and findings.
- **Behaviour:** Sets verification_status to CLEAN iff no under/over exposure and no CRITICAL/HIGH findings; otherwise EXPOSURE_IDENTIFIED. Statement and limitation are fixed text.
- **Output:** `CertificateData`.

## 7. Bureau summary builder

- **Module:** `core/reporting/bureau_summary.py`
- **Input:** run_id, ruleset_version, ExposureReport, CertificateData.
- **Output:** `BureauSummary` (run_id, ruleset_version, verification_status, underpayment_total, overpayment_total, employees_impacted, confidence_level).

## Determinism guarantees

- **No timestamps** in reports; no randomness; no AI or heuristics.
- **Same CSV + same config** → same findings, same exposure report, same certificate, same bureau summary.
- **Finding order** is fixed: sort by `rule_id`, then first `employee_ref`.
- **Config** is read from a single JSON file; validation is provided by `core/rules/config_contract.py`.

## API layer

- **Scan endpoint:** `apps/api/routers/scan.py` — POST uploads CSV, builds mapping, calls normalize → run_all → build_exposure_report → build_certificate → build_bureau_summary, returns summary, findings, run_id, input_hash, bureau_summary, exposure_breakdown. Response shape is unchanged by this phase.
