import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { runValidation } from '../api/client';
import { useScan } from '../context/ScanContext';
import { UploadDropzone } from '../components/UploadDropzone';

export function UploadPage() {
  const navigate = useNavigate();
  const { setScan } = useScan();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      const result = await runValidation(file);
      setScan(result);
      navigate('/results');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold text-gray-900 mb-2">
        Payroll Compliance Validator
      </h1>
      <p className="text-gray-600 mb-8">
        Upload payroll CSV, run validation, download the report.
      </p>

      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Upload Payroll File
        </label>
        <UploadDropzone
          onFileSelect={(f) => {
            setFile(f);
            setError(null);
          }}
          disabled={loading}
        />
      </div>

      <p className="text-gray-500 text-sm mb-2">
        CSV payroll export. Required columns: employee_id, gross_pay, net_pay.
      </p>
      <p className="text-gray-400 text-xs mb-6">
        Your payroll file is processed for validation and not permanently stored.
      </p>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={handleRun}
        disabled={!file || loading}
        className="w-full py-3 px-4 bg-gray-900 text-white font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Processing payroll...' : 'Run Validation'}
      </button>
    </div>
  );
}
