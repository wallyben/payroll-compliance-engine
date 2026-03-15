# ENGINE_AUDIT.md
**Repository:** payroll-compliance-engine
**Audit Date:** 2026-03-15
**Auditor:** Engineering Council (composite review)
**Ruleset Version:** IE-2026.01
**Git HEAD:** af37c3f (Phase 7 complete)

---

## 1. Current Pipeline Summary

The pipeline is linear, deterministic in intent, and correctly isolated by layer.

```
upload (CSV/XLSX)
  └─ load_table()          core/ingest/loader.py
       └─ normalize()      core/normalize/mapper.py + schema.py
            └─ run_all()   core/rules/engine.py  ← 30 rules, RULE_ORDER tuple
                 └─ score_bundle()    core/scoring/risk.py
                      └─ aggregate_severity_summary()  apps/api/helpers.py
                           └─ build_pdf()  core/reporting/pdf.py
                                └─ RunOut  apps/api/schemas.py
                                     └─ Run (DB)  apps/api/models.py
```

**Config loading path (two divergent implementations — see §7):**
- `core/rules/engine.py::load_ie_config()` → `encoding="utf-8-sig"` ✓
- `apps/api/config_loader.py::load_rules_config()` → `encoding="utf-8"` ✗ (BOM crash)

---

## 2. Determinism Assessment

### PASS — Core scoring path

| Component | Mechanism | Status |
|-----------|-----------|--------|
| SEVERITY_WEIGHTS | `MappingProxyType` + `Final` | PASS |
| SCORE_MAX_POINTS | `Final[int]` | PASS |
| RISK_BAND_THRESHOLDS | `MappingProxyType` + `Final` | PASS |
| Rule execution order | `RULE_ORDER` tuple + regex test | PASS |
| JSON DB payload | `json.dumps(..., sort_keys=True)` | PASS |
| PDF file size | Fixed-width ReportLab timestamp | PASS |
| compliance_score formula | Pure int arithmetic, no floats | PASS |

### FAIL — Upload storage filename hashing

`apps/api/routers/uploads.py:25`:
```python
dest = STORE / f"{abs(hash(f.filename))}_{f.filename}"
```
Python's built-in `hash()` is randomised per process (`PYTHONHASHSEED`). The stored filename changes on every server restart. This is not a compliance risk (DB stores the path), but the non-determinism means stored paths are not reproducible from inputs. A SHA256-based slug should be used instead.

### FAIL — `foo/../bar.csv` path resolves to `storage/uploads/bar.csv`

The hash prefix is bypassed when the filename contains `../` components. Two uploads with different filenames that resolve to the same path (`a/../x.csv` and `b/../x.csv`) silently overwrite each other. The extension check prevents arbitrary writes but does not prevent intra-storage overwrite. No is_relative_to guard is applied post-resolve for the upload path (unlike `report_path_for_run()` which does apply it).

### PASS — Config loading (engine path only)

`load_ie_config()` in engine.py correctly handles the UTF-8 BOM in `ie_config_2026.json` using `encoding="utf-8-sig"`. The file is confirmed to carry a BOM (`\xef\xbb\xbf`).

---

## 3. Rule Engine Stability Assessment

### Rule inventory (from `docs/rule_inventory_matrix.csv`):

| Status | Count | Rule IDs |
|--------|-------|----------|
| Implemented | 22 | IE.SANITY.001–009, IE.USC.004/006, IE.PRSI.001–005, IE.PAYE.001/003/004/005, IE.PAYSLIP.001/002 |
| Not implemented | 11 | IE.MIN_WAGE.001, IE.USC.001/002/003/005, IE.PAYE.002, IE.WORKING_TIME.001, IE.SSP.001/002, IE.AUTO_ENROL.001/002 |

**Note:** The matrix is inconsistent with the live rule code. The following rules are marked **implemented** in the matrix but are **no-ops** at runtime (always return `[]`):

| Rule ID | Function | Reason |
|---------|----------|--------|
| IE.SANITY.004 | `rule_sanity_004_deduction_breakdown_mismatch` | `deduction_breakdown` field not in `CanonicalPayrollRow` — explicitly no-op |
| IE.PAYSLIP.001 | `rule_payslip_001_missing_itemised` | Same reason — no-op by design |

These rules are registered in `RULE_ORDER`, called in `run_all()`, and counted as implemented — but they produce zero findings in all circumstances. They inflate the apparent rule count.

### CRITICAL — Duplicate logic: SANITY.001 and SANITY.006

Both rules implement an **identical check**:

```python
# rule_sanity_001_gross_deduction_consistency (line 132)
known = paye + usc + prsi_ee + pension_ee
if abs(net_pay - (gross_pay - known)) > 0.02:  # fires IE.SANITY.001

# rule_sanity_006_net_inconsistency (line 25)
known = paye + usc + prsi_ee + pension_ee
if abs(net_pay - (gross_pay - known)) > 0.02:  # fires IE.SANITY.006
```

Both fire on the same rows with the same trigger condition. A single payroll violation produces two HIGH findings from two different rule IDs. This:
- Inflates risk_points (+20 for one real violation)
- Inflates severity_summary HIGH count
- Produces confusing audit output for a regulator reviewing the report
- Is not caught by any existing test (the integration fixture does not trigger either rule)

The tests for SANITY.001 and SANITY.006 use different fixtures and do not cross-check for duplicate firing.

### Rule ordering contract

`RULE_ORDER` tuple (30 entries) is enforced against `run_all()` source code by `test_rule_execution_order.py::test_rule_order_matches_run_all_source`. Ordering is: sanity/structural → statutory bounds → plausibility. No drift detected between declaration and execution.

### Config resilience

All three previously-failing config rules (`rule_usc_plausibility`, `rule_prsi_plausibility_class_a`, `rule_prsi_deterministic_bounds`) now use `.get()` chains with `None` guards. Verified: `run_all(rows, {})` does not raise.

---

## 4. Reporting / Output Contract Assessment

### PASS — PDF output

- `build_pdf()` signature extended to accept `severity_summary`, `exposure_total`, `risk_band` (all optional, backward-compatible)
- Risk band, severity breakdown, and exposure rendered in report header when supplied
- File size is stable for identical inputs (ReportLab timestamp is fixed-width)
- PDF correctly validated in tests: magic bytes (`%PDF`), file existence, non-zero size

### PASS — findings_json DB payload

- Serialised as `json.dumps({...}, sort_keys=True)` — deterministic key ordering
- Contains both `score_bundle` and `findings` sub-keys
- Round-trip verified in tests

### PARTIAL — RunOut schema

`compliance_score` is declared as `Optional[float]` in `RunOut` but `score_bundle()` returns `int`. Pydantic coerces the int to float transparently, so no runtime error occurs. The type annotation is incorrect and misleading — it should be `Optional[int]`.

`severity_summary` is typed as `Optional[dict]` with no key constraint. A regulator inspecting the schema cannot determine what keys to expect from the type annotation alone.

### GAP — PDF path not persisted in Run model

`apps/api/models.py` has no `report_path` column. The PDF is written to `storage/reports/run_{id}.pdf` and the path is reconstructed by `report_path_for_run()`. This works, but:
- The path is not auditable from the DB without knowledge of the derivation function
- There is no DB record that a PDF was generated for a given run

### GAP — findings_json integrity hash not stored

`core/security/crypto.py` implements `sha256_of_text()` suitable for hashing `findings_json` before DB write and verifying on read. The function is not called anywhere in the API router. The `Run` model has no `findings_hash` column. The integrity module exists but is not integrated.

---

## 5. Integrity / Hash Assessment

### PASS — Hash function implementations

| Function | Status | Notes |
|----------|--------|-------|
| `sha256_of_bytes()` | PASS | Standard hashlib, doctest vector correct |
| `sha256_of_text()` | PASS | UTF-8 encoding, delegates to sha256_of_bytes |
| `sha256_of_file()` | PASS | 64KiB chunked, memory-flat for large files |
| `verify_hash()` | PASS | `hmac.compare_digest` constant-time comparison |
| `assert_hash_match()` | PASS | Raises `HashMismatchError(ValueError)` with context |

### CRITICAL — crypto.py module crashes on import in this environment

```
core/security/crypto.py:104: from cryptography.fernet import Fernet
→ pyo3_runtime.PanicException: Python API call failed
  (_cffi_backend missing)
```

This causes **collection failure for the entire `test_file_integrity.py`** file — 49 tests are uncollectable. The root cause is a broken system-level `cryptography` package (`/usr/lib/python3/dist-packages/`) installed against an incompatible pyo3/cffi version. The `pip install cryptography` installs a compatible version, but the system package takes precedence at import.

The `Fernet` import exists only to support `derive_fernet_key()`, which is a **confirmed broken placeholder**:
```python
def derive_fernet_key(secret: str) -> bytes:
    digest = sha256(secret.encode("utf-8")).digest()
    return Fernet.generate_key()[:0]  # returns b"" always
```
This function returns `b""` unconditionally. It is referenced in pyproject.toml as a dependency (`cryptography>=42.0`) but never actually used in the compliance pipeline. Its presence in `crypto.py` causes the entire module to be uncollectable in this environment.

**Impact:** 49 Phase 6 tests cannot run. The SHA256 functions are sound but their test suite is blocked.

### FAIL — derive_fernet_key() is broken by design

Even if the import succeeded, the function returns `b""`. Any code attempting to use it for encryption would silently produce empty keys. There is no caller in the current codebase, but the function should not exist in a state where calling it produces a subtly wrong result.

---

## 6. Test Coverage Summary

### Pass/fail by file (361 collected, 1 skipped, 0 failed; 49 uncollectable)

| File | Tests | Result | Coverage area |
|------|-------|--------|---------------|
| test_scoring_determinism.py | 74 | PASS | Scoring constants, weights, risk_band, exposure, determinism |
| test_full_pipeline.py | 60 | PASS | End-to-end: ingest → score → PDF, replay determinism |
| test_rule_execution_order.py | 47 | PASS | RULE_ORDER, finding shape, config loading |
| test_report_generation.py | 40 | PASS | RunOut schema, PDF generation, findings_json payload |
| test_normalization.py | 40 | PASS | normalize(), CanonicalPayrollRow validation |
| test_ingest_pipeline.py | 22 | PASS | load_table() — CSV/XLSX/encoding/validation |
| test_file_integrity.py | 49 | **UNCOLLECTABLE** | SHA256 functions — blocked by crypto import |
| test_regression_phase2.py | 6 | PASS | Rule regression |
| test_contributions.py | 2 | PASS | Auto-enrolment rule |
| test_contract_freeze.py | 3 | PASS | normalize() signature, engine module |
| test_engine_order_freeze.py | 1 | PASS | RULE_ORDER freeze |
| test_health_endpoint.py | 1 | **SKIPPED** | FastAPI not importable in test env |
| test_min_wage.py | 0 | **EMPTY** | No tests written |
| test_leave.py | 0 | **EMPTY** | No tests written |
| Per-rule unit tests (28 files) | ~67 | PASS | Individual rule behaviour |

**Totals:**
- Declared tests: 410
- Runnable and passing: 361
- Skipped: 1
- Uncollectable (import failure): 49
- Failed: 0

### Coverage gaps (no tests exist for these modules)

| Module | Gap |
|--------|-----|
| `apps/api/config_loader.py` | `load_rules_config()` BOM bug untested |
| `apps/api/security.py` | JWT creation/verification untested |
| `apps/api/deps.py` | `require_role()` enforcement untested |
| `apps/api/routers/auth.py` | Login endpoint untested |
| `apps/api/routers/uploads.py` | Upload handling untested |
| `apps/api/routers/mappings.py` | Mapping creation untested |
| `core/rules/validators.py` | `money_round()`, `require_fields()` untested |
| `core/utils/date.py` | `safe_parse_date()` tested only implicitly via normalize |

---

## 7. Regression Risk Areas

### HIGH RISK — BOM bug in production config path

`apps/api/config_loader.py::load_rules_config()` calls:
```python
RULES_CONFIG_PATH.read_text(encoding="utf-8")
```
`ie_config_2026.json` is a UTF-8 BOM file. This raises `JSONDecodeError: Unexpected UTF-8 BOM` on every API call that triggers a run in production. The engine tests pass because they use `engine.py::load_ie_config()` (which correctly uses `utf-8-sig`). The API router path is untested and broken.

**Fix:** Change `encoding="utf-8"` to `encoding="utf-8-sig"` in `config_loader.py:17`.

### HIGH RISK — SANITY.001 / SANITY.006 duplicate firing

Any payroll row where `net_pay ≠ gross - (paye + usc + prsi_ee + pension_ee)` fires both `IE.SANITY.001` and `IE.SANITY.006` simultaneously. This produces:
- +20 risk_points per violation (10+10 for two HIGH findings)
- A compliance_score that is 20 points lower than correct for the same error
- Two separate report entries for one real problem
- An auditor-visible contradiction (same violation, two rule IDs)

This will be visible on any realistic payroll file where net pay is not exactly `gross - itemised_deductions`.

### MEDIUM RISK — crypto.py module import failure blocks Phase 6 tests

The `from cryptography.fernet import Fernet` at module level means that any environment with a broken system cryptography package (as in this repo) cannot import `core.security.crypto` at all. This blocks all 49 Phase 6 tests. The fix is to move the Fernet import inside `derive_fernet_key()` or remove it entirely.

### MEDIUM RISK — upload filename path traversal bypass

A filename like `foo/../bar.csv` passes the extension check (`.csv`) and resolves to `storage/uploads/bar.csv`, bypassing the hash-prefix intended to prevent collision. No `is_relative_to` validation is applied post-resolve for uploads. Two different uploads resolving to the same path silently overwrite.

### LOW RISK — hash(filename) non-determinism

Python built-in `hash()` is randomised per-process. Upload filenames contain a `hash(filename)`-derived prefix. The prefix changes on every server restart for the same filename. This is not exploitable but means stored paths cannot be reproduced from inputs, which is a maintainability and auditability concern.

### LOW RISK — no-op rules inflate rule count

`rule_payslip_001_missing_itemised` and `rule_sanity_004_deduction_breakdown_mismatch` always return `[]`. They are listed in RULE_ORDER, appear in run_all(), and are marked as implemented in the matrix. A regulator auditing rule coverage would count them as active protections when they provide none.

---

## 8. Remaining Hardening Gaps

Ranked by priority for compliance-engine readiness:

| # | Gap | Severity | Effort |
|---|-----|----------|--------|
| 1 | `config_loader.py` BOM bug — production API crashes on every run | CRITICAL | 1 line |
| 2 | `crypto.py` Fernet import at module level — 49 tests blocked | HIGH | Move import inside function |
| 3 | SANITY.001 / SANITY.006 duplicate logic — double-fires on same rows | HIGH | Remove one or differentiate |
| 4 | `findings_hash` not stored in Run model — SHA256 module unused | HIGH | DB column + router integration |
| 5 | `derive_fernet_key()` returns `b""` — broken placeholder | HIGH | Remove or implement |
| 6 | Upload path traversal bypass for `../`-containing filenames | MEDIUM | Add `Path(fname).name` sanitisation |
| 7 | `compliance_score` typed as `Optional[float]` but is `int` | MEDIUM | Fix type annotation in RunOut |
| 8 | `severity_summary` typed as `Optional[dict]` — no key contract | MEDIUM | Type as `Optional[Dict[str, int]]` |
| 9 | `report_path` not persisted in Run model | LOW | Add column to Run |
| 10 | `hash(filename)` for upload slug — not deterministic across restarts | LOW | Use `sha256_of_text(filename)[:16]` |
| 11 | Rule matrix marks no-op rules as implemented | LOW | Update matrix or implement rules |
| 12 | No tests for auth, uploads, mappings routers | LOW | Add integration tests with TestClient |
| 13 | `test_min_wage.py`, `test_leave.py` are empty files | LOW | Populate or delete |
| 14 | 11 rules listed in matrix as not implemented: SSP, WORKING_TIME, full USC bands, PAYE.002 | SCOPE | Future phases |

---

## 9. Regulator-Defensible Internal Demo: Pass / Fail

**Verdict: CONDITIONAL PASS — core engine only; API layer has a blocking bug**

| Area | Status | Notes |
|------|--------|-------|
| Ingest layer (load_table) | **PASS** | Encoding fallback, type safety, structured errors |
| Normalization (normalize + CanonicalPayrollRow) | **PASS** | NaN/Inf rejection, empty employee_id rejection, partial-file processing |
| Rule engine (run_all, RULE_ORDER, 30 rules) | **PASS** | Deterministic ordering, finding shape contract, config resilience |
| Scoring (score_bundle, risk_band, exposure) | **PASS** | Frozen constants, deterministic formula, correct band boundaries |
| PDF reporting (build_pdf) | **PASS** | Severity/band/exposure rendered, deterministic file size |
| findings_json persistence | **PASS** | sort_keys=True, round-trip verified |
| Full pipeline determinism | **PASS** | Identical outputs on replay, 60 integration tests passing |
| Config loading (API path) | **FAIL** | BOM bug crashes every production run — 1-line fix |
| SHA256 integrity integration | **FAIL** | Module exists, functions correct, but unused and import-broken |
| SANITY.001/006 duplication | **FAIL** | Double-fires inflate score; will confuse auditors on real data |
| Test suite clean run | **FAIL** | 49 tests uncollectable; 1 test skipped; suite is not clean |
| API endpoint tests | **FAIL** | Auth, upload, mapping, run endpoints have no passing tests |

**For a regulator-defensible demo the following must be fixed before the session:**
1. `config_loader.py` BOM fix (1 line — `utf-8` → `utf-8-sig`)
2. Move `from cryptography.fernet import Fernet` inside `derive_fernet_key()` to unblock 49 tests
3. Resolve SANITY.001 / SANITY.006 — either remove the duplicate or add a clear differentiation documented for the auditor

All three are small, low-risk changes. With them applied, the core engine pipeline is defensible for a controlled internal demo with an Irish payroll bureau or a revenue authority observer.

---

## Appendix: File inventory reviewed

```
apps/api/
  config_loader.py   helpers.py   logging_config.py   main.py
  db.py   deps.py   models.py   schemas.py   security.py   settings.py
  routers/auth.py   routers/mappings.py   routers/runs.py   routers/uploads.py
core/
  ingest/loader.py
  normalize/mapper.py   normalize/schema.py
  reporting/pdf.py
  rules/engine.py   rules/rules.py   rules/validators.py   rules/ie_config_2026.json
  scoring/risk.py
  security/crypto.py
  utils/date.py
docs/
  PHASE_1_STABILITY_LOCK.md   PHASE_2_CORRECTNESS_LOCK.md
  phase5_rule_library_scope_contract.md   rule_inventory_matrix.csv
tests/
  46 test files (361 passing, 49 uncollectable, 1 skipped, 2 empty)
```
