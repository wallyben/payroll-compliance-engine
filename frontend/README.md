# Payroll Compliance Validator — Frontend

Minimal 3-screen UI for the Irish Payroll Compliance Engine. No backend changes to rule engine, API responses, or data models.

## Stack

React 18, TypeScript, Vite 5, Tailwind CSS, React Router 6.

## How to run

1. **Backend:** from repo root run `uvicorn apps.api.main:app --reload` (port 8000).
2. **Frontend:** from `frontend/` run `npm install` then `npm run dev` (port 5173).
3. Open http://localhost:5173. Vite proxies `/api` to http://localhost:8000.

To point at another backend, set `VITE_API_URL` (e.g. `http://localhost:8000`).

## Required CSV fields

Minimum columns: **employee_id**, **gross_pay**, **net_pay**. Other canonical columns (e.g. pay_date, paye, usc, prsi_ee, prsi_er) are optional; include them if your export has them.

## The 3 screens

- **Upload** — Upload payroll CSV, run validation, download the report. On success you are taken to Results.
- **Results** — Ruleset, employees affected, total findings, severity breakdown (CRITICAL → HIGH → MEDIUM → LOW), then findings table with severity/rule/employee filters and sort. When no findings, a green “Payroll passed compliance validation” banner is shown. Primary screen after a run.
- **Summary** — When no findings: Payroll Status (PASSED) card with ruleset, employees processed, validation timestamp. Total exposure and severity counts, rule breakdown table, and export: Download Compliance Report (PDF), Download Compliance Certificate (when passed), Download Findings CSV.

## Compliance Certificate

When no findings are detected, the system allows downloading a **Compliance Certificate** confirming that the payroll passed validation using ruleset IE-2026.01. On the Summary page, the “Download Compliance Certificate” button is enabled only when the run has zero findings; it calls the same report endpoint, which returns a certificate-style PDF (result PASSED, employees processed, validation reference, ruleset).

## Compliance Certificate Integrity

Certificates include a **validation timestamp** (UTC, from the backend when the scan completes), a **run identifier** (run_id), and a **certificate reference hash** (first 12 characters of SHA-256 of run_id, ruleset version, employees processed, and validated_at) to allow traceability of validation runs. The UI displays the timestamp returned by the API; it does not generate timestamps client-side.

## Report download endpoint

The UI uses **POST /scan/report**: request body is the full scan response JSON (same shape as POST /scan); response is a PDF file. When the request body has zero findings, the backend returns a compliance certificate PDF; otherwise it returns the scan report PDF. GET /scan/report is also supported. API response shape (application/pdf) is unchanged.

## Structure (short)

- `src/api/client.ts` — POST /scan, POST /scan/report.
- `src/pages/` — UploadPage, ResultsPage, SummaryPage.
- `src/components/` — FindingsTable, SeverityBadge, UploadDropzone, SummaryCard, NavBar.
- `src/context/ScanContext.tsx` — Holds last scan result for Results and Summary.
