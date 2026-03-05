# 5-Minute Demo Walkthrough

This walkthrough demonstrates the Irish Payroll Compliance Validator using the example files in `demo_data/`. Total time: about 5 minutes.

## Prerequisites

- Backend running: `uvicorn apps.api.main:app --reload` (port 8000)
- Frontend running: from `frontend/` run `npm run dev` (port 5173)
- Open http://localhost:5173

---

## Step 1 — Upload severe_issues_payroll.csv (0:00–1:00)

1. On the **Upload** screen, click or drag to select `demo_data/severe_issues_payroll.csv`.
2. Click **Run Validation**.
3. When processing finishes, you are taken to **Results**.

**What to show:** The validator runs immediately and redirects to Results. No need to configure anything.

---

## Step 2 — Show findings table (1:00–2:00)

On the **Results** page:

1. Point out **Ruleset: IE-2026.01**, **Employees affected**, and **Total findings**.
2. Show the **Severity breakdown** (CRITICAL, HIGH, MEDIUM, LOW).
3. Scroll to the **Findings** table. Show columns: Rule, Severity, Employee, Issue, Impact.
4. Use the severity filter toggles or sort by severity so CRITICAL findings are at the top.

**What to say:** "The engine has run 19 deterministic rules. Each row is a single finding: which rule fired, for which employee, and the issue. CRITICAL and HIGH need to be fixed before we can consider the payroll compliant."

---

## Step 3 — Show exposure summary (2:00–2:30)

1. Open the **Summary** tab.
2. Show **Total exposure** and **Severity counts** in the Exposure summary card.
3. Show **Exposure by rule**: Rule ID, finding count, amount impact.

**What to say:** "Exposure is the quantified risk from findings. The rule breakdown shows which rules contributed and how much."

---

## Step 4 — Explain rules (2:30–3:00)

Refer back to the findings (or the table on Summary):

- **IE.NET.001** — Net pay exceeds gross pay (CRITICAL).
- **IE.NET.002** — Negative net pay (CRITICAL).
- **IE.DATA.001** — Duplicate employee_id in the file (HIGH).
- **IE.MINWAGE.001** — Effective hourly rate below statutory minimum (HIGH).

**What to say:** "These are the kinds of issues a bureau needs to fix before submission. The validator doesn’t change data; it only flags problems."

---

## Step 5 — Fix data (3:00–3:30)

**Narrative only (no live fix in this demo):** "In a real workflow, the operator would correct the payroll in their system: fix net/gross, remove duplicates, and ensure minimum wage. Then they’d export a new CSV and run validation again."

---

## Step 6 — Upload clean_payroll.csv (3:30–4:00)

1. Go back to the **Upload** tab.
2. Select `demo_data/clean_payroll.csv`.
3. Click **Run Validation**.

**What to show:** A file with no structural violations (no net>gross, no negative net, no duplicates, min wage satisfied, PRSI class present). Depending on the active rule profile, you may see zero findings or a small number of low/medium findings.

---

## Step 7 — Show PASSED banner (4:00–4:30)

When the run has **zero findings**:

1. On **Results**, show the green banner: **"Payroll passed compliance validation"** and **"No issues were detected using ruleset IE-2026.01."**
2. If there are still some findings (e.g. from PRSI/USC plausibility), explain that the bureau would address those until the run shows 0 findings.

**What to say:** "When there are no findings, the payroll is considered compliant for this ruleset and the certificate becomes available."

---

## Step 8 — Download compliance certificate (4:30–5:00)

1. Open the **Summary** tab.
2. Show the **Payroll Status** card: **PASSED**, ruleset, employees processed, validation timestamp.
3. Click **Download Compliance Certificate**.
4. Open the PDF and briefly show: Result PASSED, ruleset, validation reference, certificate reference hash, validation timestamp, and the liability footer.

**What to say:** "The certificate is audit-credible: it includes a backend timestamp and a certificate reference hash so the run can be traced. This is what a bureau can keep on file or share with clients."

---

## Demo tips

- Keep the **Results** tab as the main view after each run; use **Summary** for exposure and export.
- If `clean_payroll.csv` still shows findings (profile-dependent), say: "One more fix in the source data would bring this to zero and unlock the certificate."
- For a strict 0-findings run, use a file that has already been corrected in a previous validation pass.
