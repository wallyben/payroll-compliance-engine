import React, { createContext, useCallback, useContext, useState } from 'react';
import type { ScanResponse } from '../api/client';

interface ScanContextValue {
  scan: ScanResponse | null;
  validatedAt: string | null;
  setScan: (s: ScanResponse | null) => void;
  clearScan: () => void;
}

const ScanContext = createContext<ScanContextValue | null>(null);

export function ScanProvider({ children }: { children: React.ReactNode }) {
  const [scan, setScanState] = useState<ScanResponse | null>(null);
  const setScan = useCallback((s: ScanResponse | null) => setScanState(s), []);
  const clearScan = useCallback(() => setScanState(null), []);
  const validatedAt = scan?.validated_at ?? null;
  return (
    <ScanContext.Provider value={{ scan, validatedAt, setScan, clearScan }}>
      {children}
    </ScanContext.Provider>
  );
}

export function useScan() {
  const ctx = useContext(ScanContext);
  if (!ctx) throw new Error('useScan must be used within ScanProvider');
  return ctx;
}
