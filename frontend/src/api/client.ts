/**
 * API client for existing backend. No changes to backend contract.
 * POST /scan → upload CSV, get summary + findings + bureau_summary + exposure_breakdown
 * POST /scan/report → body: full scan response JSON → returns PDF
 */

const API_BASE = import.meta.env.VITE_API_URL ?? '/api';

export interface Finding {
  rule_id: string;
  severity: string;
  title: string;
  description?: string;
  employee_refs?: string[];
  amount_impact?: number | null;
  category?: string;
}

export interface ScanSummary {
  total_findings: number;
  critical: number;
  warning: number;
  info: number;
  overall: string;
}

export interface BureauSummary {
  run_id: string;
  ruleset_version: string;
  verification_status: string;
  underpayment_total: number;
  overpayment_total: number;
  employees_impacted: number;
  confidence_level: string;
}

export interface ExposureRuleBreakdown {
  rule_id: string;
  finding_count: number;
  exposure_weight: number;
  total_amount_impact: number;
}

export interface ExposureBreakdown {
  underpayment_total: number;
  overpayment_total: number;
  total_exposure: number;
  employees_impacted: number;
  quantifiable_findings: number;
  non_quantifiable_findings: number;
  confidence_level: string;
  severity_counts: Record<string, number>;
  rule_breakdown: ExposureRuleBreakdown[];
  categories?: unknown[];
}

export interface ScanResponse {
  summary: ScanSummary;
  all_findings: Finding[];
  run_id: string;
  validated_at?: string;
  bureau_summary: BureauSummary;
  exposure_breakdown: ExposureBreakdown;
  auto_enrolment_findings?: Finding[];
  revenue_findings?: Finding[];
  input_hash?: string;
}

export async function runValidation(file: File): Promise<ScanResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/scan/`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const message = Array.isArray(detail)
      ? detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join('; ') || res.statusText
      : typeof detail === 'string'
        ? detail
        : res.statusText;
    throw new Error(message || 'Validation failed');
  }
  return res.json();
}

export async function downloadReportPdf(scanResponse: ScanResponse): Promise<Blob> {
  const res = await fetch(`${API_BASE}/scan/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scanResponse),
  });
  if (!res.ok) throw new Error('Report download failed');
  return res.blob();
}
