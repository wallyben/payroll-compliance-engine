# PHASE 5 — RULE LIBRARY SCOPE CONTRACT
Version: v0.5.0-draft
Status: Draft
Branch: phase5-rule-library-foundation

---

## 1. Objective

Define a comprehensive Irish payroll validation rule library that:
- Detects all payroll errors within defined scope
- Is deterministic
- Is table-driven where rates change by year
- Produces defensible compliance findings
- Never silently passes missing required data

---

## 2. Scope Boundary (In Scope)

### A. Statutory Wage Compliance
- National Minimum Wage validation
- Hourly rate validation (if hours provided)

### B. Statutory Deduction Sanity
- USC validation (band + threshold accuracy by tax year)
- PRSI validation (class + threshold accuracy by tax year)
- PAYE tax negative / impossible combinations detection

### C. Payslip Compliance
- Gross pay present
- Itemised deductions present
- Net pay consistency check

### D. Working Time (If Hours Provided)
- 48-hour average weekly limit validation

### E. Statutory Sick Pay (If Leave Data Provided)
- SSP eligibility / entitlement validation (table-driven)

---

## 3. Explicitly Out of Scope (Unless Configured)

- Sectoral ERO/REA rates
- Union agreements
- Contractual overtime rates
- Collective bargaining rules
- Non-Irish payroll legislation
- Manual employment contract interpretation

---

## 4. Data Reality Contract

Each rule must define:
- required_fields
- config_tables_required
- tax_year_dependency (if applicable)

If required_fields are missing:
→ Emit DATA.MISSING.<RULE_ID> finding
→ Do NOT silently pass

---

## 5. Rule Architecture Standards

Every rule must include:
- rule_id
- category
- description
- required_fields
- severity
- evidence_payload
- test_fixture_reference

Rule IDs must be:
IE.<CATEGORY>.<XXX>

Example:
IE.USC.001
IE.MINWAGE.001
IE.PAYSLIP.001

---

## 6. Rate & Threshold Handling

All tax year sensitive values must:
- Be externalised to tables (JSON/YAML)
- Be versioned by tax_year
- Not hardcoded in rule logic

---

## 7. Test Coverage Requirements

For every rule:
- Minimum 1 failing fixture
- Minimum 1 passing fixture
- Rule ID must appear in at least one test
- Snapshot regression protection required

---

## 8. Definition of “Comprehensive Within Scope”

Comprehensive means:
- Every statutory payroll validation rule detectable from available input data
- No silent pass conditions
- No duplicated rule logic
- Deterministic output
- Version-controlled rule library

---

End of document.
