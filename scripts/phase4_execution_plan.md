# Phase 4 — Bureau Compliance Shield Packaging Layer
Branch: phase4-bureau-shield
Repository: payroll_compliance_v1_scaffold

Status: Phase 3 stable (83 passing tests)
Objective: Add Bureau Shield reporting layer without modifying validation engine.

STRICT RULES:
- Do NOT refactor validation logic.
- Do NOT change existing response fields.
- Only ADD reporting layer.
- Preserve deterministic guarantees.
- All new modules must be pure + unit tested.
- No randomness.
- No timestamps inside reporting layer.
- Stable ordering required.
- No new external dependencies.
- All previous tests must continue passing.

---

# Gate 1 — Hashing Module

Create:
core/reporting/hash_utils.py

Function:
compute_sha256_bytes(data: bytes) -> str

Requirements:
- Use hashlib.sha256
- Lowercase hex digest
- Deterministic
- No side effects

Create:
tests/test_phase4_hash_utils.py

Test:
- Known test vector
- Deterministic repeat calls

Acceptance:
- All tests pass.

STOP after completion.

---

# Gate 2 — Exposure Engine

Create:
core/reporting/exposure_engine.py

Dataclasses:

ExposureCategoryBreakdown:
    category: str
    underpayment_total: float
    overpayment_total: float
    employees_impacted: int
    quantifiable_findings: int
    non_quantifiable_findings: int

ExposureReport:
    underpayment_total: float
    overpayment_total: float
    categories: list[ExposureCategoryBreakdown]
    employees_impacted: int
    quantifiable_findings: int
    non_quantifiable_findings: int
    confidence_level: str  # HIGH | MEDIUM | LOW

Rules:
- Only compute deltas if numeric values present.
- Never invent amounts.
- Never net under/over totals.
- Group by finding.category.
- Distinct employee_ids count.
- Confidence:
    HIGH = all quantifiable
    MEDIUM = <=20% non_quantifiable
    LOW = >20% non_quantifiable
- Stable ordering by category name.

Create:
tests/test_phase4_exposure_engine.py

Test:
- Clean run
- Mixed findings
- LOW confidence case
- Stable ordering

Acceptance:
- All tests pass.

STOP after completion.

---

# Gate 3 — Certificate Builder

Create:
core/reporting/certificate_builder.py

Define:

VerificationStatus:
    CLEAN
    EXPOSURE_IDENTIFIED

CertificateData:
    verification_status: str
    statement: str
    limitation: str

Logic:
CLEAN if:
    underpayment_total == 0
    AND overpayment_total == 0
    AND no critical findings

Statements:
CLEAN:
"Based on deterministic validation against the specified ruleset, no statutory payroll calculation irregularities were detected within the scope of the applied rule library."

EXPOSURE:
"Deterministic validation identified statutory payroll calculation irregularities within the applied ruleset. Quantified exposure is detailed in the accompanying summary."

Limitation (always included):
"This validation is limited to deterministic rule-based analysis of the supplied payroll dataset and does not constitute legal advice."

Create:
tests/test_phase4_certificate_builder.py

Acceptance:
- Tests pass.
- No randomness.

STOP after completion.

---

# Gate 4 — Bureau Summary Builder

Create:
core/reporting/bureau_summary.py

Define:

BureauSummary:
    run_id: str
    ruleset_version: str
    verification_status: str
    underpayment_total: float
    overpayment_total: float
    employees_impacted: int
    confidence_level: str

Function:
build_bureau_summary(...)

Create:
tests/test_phase4_bureau_summary.py

Acceptance:
- Deterministic output.
- Tests pass.

STOP after completion.

---

# Gate 5 — Audit Pack Builder

Create:
core/reporting/audit_pack_builder.py

Function:
build_audit_pack(...) -> dict[str, bytes]

Return:

{
  "summary.json": ...,
  "exposure_breakdown.json": ...,
  "findings.json": ...,
  "rules_version.txt": ...,
  "input_hash.txt": ...
}

Use:
json.dumps(sort_keys=True, indent=2)
UTF-8 encoding.
No file writes.

Create:
tests/test_phase4_audit_pack_builder.py

Acceptance:
- Stable JSON output.
- Snapshot-like shape test.
- All tests pass.

STOP after completion.

---

# Gate 6 — API Integration

Modify:
apps/api/routers/scan.py

After validation:

1. Compute input_hash from raw upload bytes.
2. Generate ExposureReport.
3. Generate CertificateData.
4. Generate BureauSummary.

Add new response keys:

{
  "run_id": "...",
  "input_hash": "...",
  "bureau_summary": {...},
  "exposure_breakdown": {...}
}

Do NOT remove existing "summary" key.
Maintain backward compatibility.

Acceptance:
- All previous tests pass unchanged.
- New Phase 4 tests pass.
- Deterministic behaviour verified.
- No dependency expansion.

END OF PHASE 4.