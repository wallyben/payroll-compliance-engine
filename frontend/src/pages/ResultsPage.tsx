import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useScan } from '../context/ScanContext';
import { FindingsTable } from '../components/FindingsTable';
import { SeverityBadge } from '../components/SeverityBadge';

export function ResultsPage() {
  const { scan } = useScan();
  const navigate = useNavigate();

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
  const counts = exposure_breakdown?.severity_counts ?? {};
  const critical = counts.CRITICAL ?? 0;
  const high = counts.HIGH ?? 0;
  const medium = counts.MEDIUM ?? 0;
  const low = counts.LOW ?? 0;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {all_findings.length === 0 && (
        <div className="mb-8 p-6 rounded-lg border-2 border-green-600 bg-green-50 text-center">
          <div className="text-green-600 text-4xl mb-2" aria-hidden>✓</div>
          <p className="text-lg font-semibold text-green-800">
            Payroll passed compliance validation
          </p>
          <p className="text-green-700 mt-1">
            No issues were detected using ruleset IE-2026.01.
          </p>
        </div>
      )}

      <div className="mb-8 space-y-4">
        <div className="flex flex-wrap gap-6 items-baseline">
          <span className="text-gray-600">
            <strong>Ruleset:</strong> {bureau_summary.ruleset_version}
          </span>
          <span className="text-gray-600">
            <strong>Employees affected:</strong> {bureau_summary.employees_impacted}
          </span>
          <span className="text-gray-600">
            <strong>Total findings:</strong> {all_findings.length}
          </span>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <span className="text-sm font-medium text-gray-500">Severity breakdown:</span>
          <span className="flex items-center gap-2">
            <SeverityBadge severity="CRITICAL" /> {critical}
          </span>
          <span className="flex items-center gap-2">
            <SeverityBadge severity="HIGH" /> {high}
          </span>
          <span className="flex items-center gap-2">
            <SeverityBadge severity="MEDIUM" /> {medium}
          </span>
          <span className="flex items-center gap-2">
            <SeverityBadge severity="LOW" /> {low}
          </span>
        </div>
      </div>

      {all_findings.length > 0 && (
        <p className="text-gray-500 text-sm mb-3">
          Fix issues in payroll system, then re-run validation.
        </p>
      )}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Findings</h2>
      <FindingsTable findings={all_findings} />
    </div>
  );
}
