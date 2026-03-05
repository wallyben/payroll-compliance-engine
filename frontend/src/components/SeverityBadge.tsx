import React from 'react';

const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white',
  HIGH: 'bg-orange-500 text-white',
  MEDIUM: 'bg-amber-400 text-gray-900',
  LOW: 'bg-gray-400 text-white',
};

export function SeverityBadge({ severity }: { severity: string }) {
  const key = (severity || '').toUpperCase();
  const style = SEVERITY_STYLES[key] ?? 'bg-gray-300 text-gray-700';
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-sm font-medium ${style}`}
      data-severity={key}
    >
      {key || '—'}
    </span>
  );
}
