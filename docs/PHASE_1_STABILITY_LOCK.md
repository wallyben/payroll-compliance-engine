
# 📄 PHASE 1 LOCK DOCUMENT

**Project:** Irish Payroll Compliance SaaS
**Ruleset Version:** IE-2026.01
**Phase:** 1 — Stability Hardening
**Status:** LOCKED
**Date Locked:** 2026-02-18

---

# 1️⃣ Phase Objective

Ensure the system:

* Never crashes on malformed payroll data
* Never returns raw stack traces
* Processes partially valid files
* Maintains deterministic behavior
* Cleanly separates:

  * Ingestion
  * Normalization
  * Validation
  * Rule evaluation
* Preserves ruleset versioning
* Returns structured, stable API responses

Phase 1 focuses strictly on reliability — not feature expansion.

---

# 2️⃣ Architecture State (Frozen)

## Core Flow

Upload → Load Table → Normalize → Validate → Rules Engine → Risk Score → Persist Run → Build PDF → Return Structured Response

---

## A. Ingestion Layer

### File: `core/ingest/loader.py`

* Supports: `.csv`, `.xlsx`, `.xls`
* Rejects unsupported file types
* Does not perform business validation

---

## B. Date Normalization

### File: `core/utils/date.py`

Function:

```
safe_parse_date(value)
```

Supports:

* YYYY-MM-DD
* DD/MM/YYYY
* MM/DD/YYYY (via dateutil)
* Excel serial numbers (int/float)

Behavior:

* Returns `date`
* Raises `ValueError` for invalid format
* Never crashes application

---

## C. Normalization Layer

### File: `core/normalize/mapper.py`

### normalize() signature (locked):

```
normalize(df, mapping) -> (valid_rows, invalid_rows)
```

Behavior:

* Validates required canonical fields:

  * employee_id
  * gross_pay
  * net_pay

* Ensures mapped columns exist

* Coerces numeric fields safely

* Parses date fields via `safe_parse_date`

* Wraps model instantiation in try/except

* Captures row-level errors

* Continues processing after invalid rows

No row-level exception can crash the run.

---

## D. Canonical Model

### File: `core/normalize/schema.py`

* Pydantic model
* Deterministic field validation
* No raw ValidationErrors bubble to API

---

## E. API Contract (Locked)

### RunOut Schema

```
class RunOut(BaseModel):
    id: int
    upload_id: int
    mapping_id: int
    ruleset_version: str
    findings: List[Finding]
    counts: Dict[str, int]
    invalid_rows: List[Dict[str, Any]]
```

Guaranteed Response Structure:

```
{
  id,
  upload_id,
  mapping_id,
  ruleset_version,
  findings: [],
  counts: {
    total,
    valid,
    invalid
  },
  invalid_rows: []
}
```

API never returns stack traces.

---

## F. Mapping Validation

Unknown canonical fields:
→ 400 Bad Request

Example:

```
Unknown canonical field: additionalProp1
```

This is correct behavior.

---

## G. Rule Engine Isolation

### File: `core/rules/engine.py`

* Only receives valid_rows
* Never receives invalid data
* Cannot crash due to normalization issues

Rules remain versioned:

```
IE-2026.01
```

---

## H. Database State

Tables:

* users
* uploads
* mappings
* runs
* audit_logs

Users:

* password_hash stored
* created_at enforced NOT NULL

JWT authentication working.

---

# 3️⃣ Stability Guarantees

The system has been tested with:

* Valid payroll file
* Invalid date formats
* Garbage strings in numeric fields
* Mixed valid/invalid rows
* Empty file
* Corrupt-style row
* Large file (2000 rows)
* Unknown mapping fields

Results:

* No 500 errors
* No application crash
* No raw Pydantic exception
* Partial file processing succeeds
* Structured invalid row reporting works
* PDF generation unaffected

---

# 4️⃣ What Phase 1 Explicitly Does NOT Include

* UI improvements
* Mapping auto-detection
* Advanced Excel heuristics
* Performance tuning beyond functional stability
* Additional compliance rules
* Integration layers
* Pricing logic
* Multi-tenant logic
* Audit trace IDs

These belong to future phases.

---

# 5️⃣ Drift Control Rules

From this point forward:

* Do not refactor normalization layer without documented justification
* Do not change API contract for RunOut
* Do not alter ruleset versioning mechanism
* Do not merge Phase 2 work into Phase 1 files
* All new features must preserve Phase 1 stability guarantees

---

# 6️⃣ Exit Criteria Confirmation

Phase 1 is considered complete because:

* System survives malformed payroll input
* Partial file processing implemented
* Deterministic error reporting enforced
* No ingestion-level crash possible
* API response contract stable
* PDF generation remains operational

---

# 7️⃣ Phase 1 Maturity Level

This ingestion layer is:

* Suitable for controlled pilot with Irish payroll bureaus
* Structurally production-safe
* Deterministic under malformed input
* Regulator-defensible at the ingestion layer


