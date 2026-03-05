import React, { useMemo, useState } from 'react';
import type { Finding } from '../api/client';
import { SeverityBadge } from './SeverityBadge';

/** Severity ordering: CRITICAL → HIGH → MEDIUM → LOW (not alphabetical). */
const severityOrder: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const;

function formatImpact(value: number | null | undefined): string {
  if (value == null) return '—';
  return `€${Number(value).toFixed(2)}`;
}

function firstEmployee(refs: string[] | undefined): string {
  if (!refs?.length) return '—';
  return refs[0];
}

interface FindingsTableProps {
  findings: Finding[];
}

export function FindingsTable({ findings }: FindingsTableProps) {
  const [ruleFilter, setRuleFilter] = useState('');
  const [employeeFilter, setEmployeeFilter] = useState('');
  const [sortBy, setSortBy] = useState<'severity' | 'rule'>('severity');
  const [severityFilter, setSeverityFilter] = useState<Set<string>>(new Set(SEVERITIES));

  const toggleSeverity = (sev: string) => {
    setSeverityFilter((prev) => {
      const next = new Set(prev);
      if (next.has(sev)) next.delete(sev);
      else next.add(sev);
      if (next.size === 0) return new Set(SEVERITIES);
      return next;
    });
  };

  const filtered = useMemo(() => {
    let list = [...findings];
    if (severityFilter.size < SEVERITIES.length) {
      list = list.filter((f) =>
        severityFilter.has((f.severity ?? '').toUpperCase())
      );
    }
    if (ruleFilter.trim()) {
      const q = ruleFilter.trim().toLowerCase();
      list = list.filter((f) => (f.rule_id ?? '').toLowerCase().includes(q));
    }
    if (employeeFilter.trim()) {
      const q = employeeFilter.trim();
      list = list.filter((f) =>
        (f.employee_refs ?? []).some((r) => String(r).includes(q))
      );
    }
    if (sortBy === 'severity') {
      list.sort(
        (a, b) =>
          (severityOrder[(a.severity ?? '').toUpperCase()] ?? 99) -
          (severityOrder[(b.severity ?? '').toUpperCase()] ?? 99)
      );
    } else {
      list.sort((a, b) =>
        (a.rule_id ?? '').localeCompare(b.rule_id ?? '')
      );
    }
    return list;
  }, [findings, ruleFilter, employeeFilter, sortBy, severityFilter]);

  if (findings.length === 0) {
    return (
      <div className="text-gray-500 py-8 text-center">
        No findings. Payroll passed validation.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <span className="text-sm text-gray-500">Severity:</span>
        {SEVERITIES.map((sev) => (
          <button
            key={sev}
            type="button"
            onClick={() => toggleSeverity(sev)}
            className={`px-2 py-1 text-xs rounded border ${severityFilter.has(sev) ? 'bg-gray-200 border-gray-300 font-medium' : 'bg-white border-gray-200 text-gray-500'}`}
          >
            {sev}
          </button>
        ))}
        <span className="text-gray-300">|</span>
        <input
          type="text"
          placeholder="Rule"
          value={ruleFilter}
          onChange={(e) => setRuleFilter(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm w-36"
        />
        <input
          type="text"
          placeholder="Employee"
          value={employeeFilter}
          onChange={(e) => setEmployeeFilter(e.target.value)}
          className="border border-gray-300 rounded px-2 py-1 text-sm w-32"
        />
        <span className="text-gray-300">|</span>
        <button
          type="button"
          onClick={() => setSortBy('severity')}
          className={`px-2 py-1 text-sm rounded ${sortBy === 'severity' ? 'bg-gray-200 font-medium' : 'bg-gray-100'}`}
        >
          By severity
        </button>
        <button
          type="button"
          onClick={() => setSortBy('rule')}
          className={`px-2 py-1 text-sm rounded ${sortBy === 'rule' ? 'bg-gray-200 font-medium' : 'bg-gray-100'}`}
        >
          By rule
        </button>
      </div>
      <div className="border border-gray-200 rounded-lg overflow-auto max-h-[70vh]">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-gray-100 border-b border-gray-200 z-10">
            <tr>
              <th className="px-4 py-3 font-semibold text-gray-700">Rule</th>
              <th className="px-4 py-3 font-semibold text-gray-700">Severity</th>
              <th className="px-4 py-3 font-semibold text-gray-700">Employee</th>
              <th className="px-4 py-3 font-semibold text-gray-700">Issue</th>
              <th className="px-4 py-3 font-semibold text-gray-700">Impact</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f, i) => (
              <tr
                key={`${f.rule_id}-${firstEmployee(f.employee_refs)}-${i}`}
                className="border-b border-gray-100 hover:bg-gray-50"
              >
                <td className="px-4 py-3 font-mono text-gray-800 whitespace-nowrap">{f.rule_id ?? '—'}</td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <SeverityBadge severity={f.severity ?? ''} />
                </td>
                <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                  {firstEmployee(f.employee_refs)}
                </td>
                <td className="px-4 py-3 text-gray-700 max-w-xs break-words">
                  {f.title ?? f.description ?? '—'}
                </td>
                <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                  {formatImpact(f.amount_impact)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length < findings.length && (
        <p className="text-gray-500 text-sm">
          Showing {filtered.length} of {findings.length} findings
        </p>
      )}
    </div>
  );
}
