import React from 'react';

interface SummaryCardProps {
  title: string;
  children: React.ReactNode;
}

export function SummaryCard({ title, children }: SummaryCardProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
        {title}
      </h3>
      {children}
    </div>
  );
}
