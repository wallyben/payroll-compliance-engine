# PHASE 5 — RULE LIBRARY SCOPE CONTRACT
Version: v0.6.0
Status: Governance
Branch: phase5-rule-library-foundation

---

## 1. Objective

Define a comprehensive Irish payroll validation rule library that:
- Detects payroll errors within the defined scope using available input data only
- Is deterministic and auditable
- Is table-driven where rates or thresholds vary by tax year
- Produces defensible, evidence-backed compliance findings
- Never silently passes when required data is missing

---

## 2. Scope Boundary (In Scope)

### A. Statutory Wage Compliance
- National Minimum Wage validation
- Hourly rate validation (when hours are provided)

### B. Statutory Deduction Sanity
- **USC:** Band and threshold accuracy by tax year; validation logic structure: apply configured bands in order, compare computed USC to supplied USC, flag breaches and mis-banding
- **PRSI:** Class and threshold accuracy by tax year; **class mismatch detection** where deduction pattern or thresholds are inconsistent with the declared or inferred PRSI class
- **PAYE:** **Negative or impossible tax amounts**; **net/gross consistency** and **PAYE-vs-net sanity checks** (e.g. PAYE + other deductions vs gross and net)

### C. Payslip Compliance
- Gross pay present
- Itemised deductions present
- Net pay consistency check (gross minus deductions vs net)

### D. Working Time (If Hours Provided)
- 48-hour average weekly limit validation

### E. Statutory Sick Pay (If Leave Data Provided)
- SSP eligibility and entitlement validation (table-driven)

---

## 3. Explicitly Out of Scope (Unless Configured)

- Sectoral ERO/REA rates
- Union agreements
- Contractual overtime rates
- Collective bargaining rules
- Non-Irish payroll legislation
- Manual employment contract interpretation
- SaaS features, multi-tenant dashboards, or productised reporting beyond validation outputs

---

## 4. Data Reality Contract

### 4.1 Obligations

Each rule **must** declare and respect:
- **required_fields:** Canonical field names without which the rule cannot be evaluated meaningfully
- **config_tables_required:** Any rate/threshold tables and their tax_year scope
- **tax_year_dependency:** Whether the rule depends on a specific tax year (and from where that year is supplied)

### 4.2 Missing Required Data

When one or more **required_fields** are missing for a row:
- Emit a finding: **DATA.MISSING.<RULE_ID>** (or equivalent as per rule ID scheme)
- Do **not** silently pass; do **not** infer or substitute values for missing fields
- Severity and evidence must allow an auditor to see that the failure was due to missing input, not to a passed validation

### 4.3 Single Source of Truth

- Required-field and config requirements are the single source of truth for what the rule needs
- No rule may assume optional fields are present unless explicitly out of scope for that rule
- Config tables must be versioned by tax year; rule logic must not hardcode rates or thresholds

### 4.4 Auditability

- Every finding must reference **rule_id**, **evidence** (e.g. inputs and thresholds used), and **severity**
- Data reality failures (missing required data) must be distinguishable from positive breach findings

---

## 5. Rule Architecture Standards

Every rule must include:
- **rule_id** (see naming below)
- **category**
- **description**
- **required_fields**
- **severity** (HIGH | MEDIUM | LOW)
- **evidence_payload**
- **test_fixture_reference**

Rule IDs: **IE.<CATEGORY>.<NNN>**

Examples: IE.USC.001, IE.PRSI.002, IE.MINWAGE.001, IE.PAYSLIP.001, IE.GROSS_NET.001

---

## 6. Rule Category Matrix

| Category        | Purpose                                      | Example rule IDs (illustrative) | Config dependency        |
|----------------|----------------------------------------------|----------------------------------|--------------------------|
| GROSS_NET      | Gross/net and deduction consistency          | IE.GROSS_NET.001                 | None                     |
| ANOMALY        | Negative/zero pay, impossible values          | IE.ANOMALY.001, IE.ANOMALY.002   | None                     |
| USC            | USC bands, thresholds, deterministic bounds  | IE.USC.001, IE.USC.002           | usc (bands, exemption)   |
| PRSI           | PRSI class, thresholds, bounds, class match | IE.PRSI.001, IE.PRSI.002        | prsi (class rates, thresholds) |
| NET            | Net pay upper bound vs gross minus deductions | IE.NET.002                      | —                        |
| PAYE           | PAYE bounds, negative tax, net sanity        | IE.PAYE.002                      | income_tax               |
| MINWAGE        | National minimum wage                         | IE.MINWAGE.001                   | minimum_wage             |
| AUTOENROL      | Auto-enrolment eligibility/deduction         | IE.AUTOENROL.001                 | auto_enrolment           |
| PAYSLIP        | Payslip completeness (future)                 | IE.PAYSLIP.*                     | As needed                |
| SSP            | Statutory sick pay (when leave data provided) | IE.SSP.*                         | As needed                |
| WORKING_TIME   | 48-hour limit (when hours provided)           | IE.WTIME.*                       | As needed                |

*This matrix defines categories and config expectations; it does not create or modify rule logic.*

---

## 7. Rate & Threshold Handling

All tax-year-sensitive values must:
- Be externalised to config tables (e.g. JSON/YAML)
- Be versioned by **tax_year**
- Not be hardcoded in rule logic

---

## 8. Test Coverage Requirements

For every rule:
- Minimum one failing fixture
- Minimum one passing fixture
- Rule ID must appear in at least one test
- Snapshot or regression protection required

---

## 9. Definition of “Comprehensive Within Scope” (Legally Defensible)

**Comprehensive within scope** means:

1. **Scope-limited:** The library covers every *in-scope* validation type listed in §2 that is implemented and that can be evaluated using the **declared required_fields** and **config_tables_required**. It does not claim to cover out-of-scope matters (§3).

2. **No silent pass:** No rule may report a “pass” or omit a finding when required input data is missing; missing-data cases result in DATA.MISSING (or equivalent) findings as per §4.2.

3. **Deterministic and auditable:** Outputs are deterministic for given inputs and config; every finding is traceable to rule_id, evidence, and config version.

4. **Version-controlled:** Rules and config tables are under version control; changes are traceable and test coverage is maintained per §8.

5. **No overclaim:** “Comprehensive” is limited to the validation types and logic implemented within this contract. It does not constitute a guarantee that all possible real-world payroll errors will be detected, nor that the system is suitable for any particular legal or regulatory purpose without independent verification.

---

End of document.
