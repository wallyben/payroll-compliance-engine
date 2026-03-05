import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScan } from '../context/ScanContext';
import { downloadReportPdf } from '../api/client';
import { SummaryCard } from '../components/SummaryCard';

function downloadCsv(findings: Array<Record<string, unknown>>) {
  if (findings.length === 0) return;
  const headers = ['rule_id', 'severity', 'employee_refs', 'title', 'amount_impact'];
  const rows = findings.map((f) =>
    headers.map((h) => {
      const v = f[h];
      if (h === 'employee_refs' && Array.isArray(v)) return v.join(';');
      return v != null ? String(v) : '';
    })
  );
  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'findings.csv';
  a.click();
  URL.revokeObjectURL(url);
}

export function SummaryPage() {
  const { scan, validatedAt } = useScan();
  const navigate = useNavigate();
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingCert, setDownloadingCert] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  if (!scan) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-12 text-center">
        <p className="text-gray-500 mb-4">No validation results. Upload a payroll file to run validation.</p>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-gray-900 font-medium underline"
        >
          Upload a payroll file
        </button>
      </div>
    );
  }

  const { bureau_summary, exposure_breakdown, all_findings } = scan;
  const totalExposure = exposure_breakdown?.total_exposure ?? 0;
  const ruleBreakdown = exposure_breakdown?.rule_breakdown ?? [];
  const severityCounts = exposure_breakdown?.severity_counts ?? {};
  const passed = all_findings.length === 0;

  const handleDownloadReport = async () => {
    setPdfError(null);
    setDownloadingPdf(true);
    try {
      const blob = await downloadReportPdf(scan);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'validation_report.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setPdfError('Failed to generate report');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleDownloadCertificate = async () => {
    if (!passed) return;
    setPdfError(null);
    setDownloadingCert(true);
    try {
      const blob = await downloadReportPdf(scan);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'compliance_certificate.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setPdfError('Failed to generate certificate');
    } finally {
      setDownloadingCert(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
      {passed && (
        <SummaryCard title="Payroll Status">
          <div className="text-center py-2">
            <p className="text-2xl font-bold text-green-700 mb-2">PASSED</p>
            <p className="text-gray-700 mb-3">
              This payroll file passed compliance validation.
            </p>
            <p className="text-sm text-gray-600">Ruleset: {bureau_summary.ruleset_version}</p>
            <p className="text-sm text-gray-600">Employees processed: {bureau_summary.employees_impacted}</p>
            {validatedAt && (
              <p className="text-sm text-gray-500 mt-1">
                Validation timestamp: {new Date(validatedAt).toLocaleString()}
              </p>
            )}
          </div>
        </SummaryCard>
      )}

      <SummaryCard title="Exposure summary">
        <div className="space-y-3 text-gray-700">
          <p>
            <strong>Total exposure:</strong> €{totalExposure.toFixed(2)}
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span><strong>CRITICAL:</strong> {severityCounts.CRITICAL ?? 0}</span>
            <span><strong>HIGH:</strong> {severityCounts.HIGH ?? 0}</span>
            <span><strong>MEDIUM:</strong> {severityCounts.MEDIUM ?? 0}</span>
            <span><strong>LOW:</strong> {severityCounts.LOW ?? 0}</span>
          </div>
        </div>
      </SummaryCard>

      <SummaryCard title="Exposure by rule">
        <div className="border border-gray-200 rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200">
                <th className="px-4 py-2 text-left font-semibold text-gray-700">Rule ID</th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700">Finding count</th>
                <th className="px-4 py-2 text-right font-semibold text-gray-700">Amount impact</th>
              </tr>
            </thead>
            <tbody>
              {ruleBreakdown.map((r) => (
                <tr key={r.rule_id} className="border-b border-gray-100">
                  <td className="px-4 py-2 font-mono">{r.rule_id}</td>
                  <td className="px-4 py-2">{r.finding_count}</td>
                  <td className="px-4 py-2 text-right">€{r.total_amount_impact.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {ruleBreakdown.length === 0 && (
            <p className="px-4 py-6 text-gray-500 text-center">No rule breakdown</p>
          )}
        </div>
      </SummaryCard>

      <SummaryCard title="Export options">
        <div className="flex flex-wrap gap-4">
          <button
            type="button"
            onClick={handleDownloadReport}
            disabled={downloadingPdf}
            className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {downloadingPdf ? 'Generating…' : 'Download Compliance Report (PDF)'}
          </button>
          <button
            type="button"
            onClick={handleDownloadCertificate}
            disabled={!passed || downloadingCert}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {downloadingCert ? 'Generating…' : 'Download Compliance Certificate'}
          </button>
          <button
            type="button"
            onClick={() => downloadCsv(all_findings)}
            disabled={all_findings.length === 0}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Download Findings CSV
          </button>
        </div>
        {pdfError && (
          <p className="mt-2 text-sm text-red-600">{pdfError}</p>
        )}
      </SummaryCard>
    </div>
  );
}
