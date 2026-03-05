import React, { useCallback, useState } from 'react';

interface UploadDropzoneProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
  accept?: string;
}

export function UploadDropzone({
  onFileSelect,
  disabled = false,
  accept = '.csv',
}: UploadDropzoneProps) {
  const [drag, setDrag] = useState(false);
  const [selectedName, setSelectedName] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File | null) => {
      if (!file) return;
      if (!file.name.toLowerCase().endsWith('.csv')) {
        return;
      }
      setSelectedName(file.name);
      onFileSelect(file);
    },
    [onFileSelect]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDrag(false);
      if (disabled) return;
      const f = e.dataTransfer.files[0];
      handleFile(f ?? null);
    },
    [disabled, handleFile]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDrag(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
  }, []);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      handleFile(f ?? null);
      e.target.value = '';
    },
    [handleFile]
  );

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      className={`
        border-2 border-dashed rounded-lg p-12 text-center transition-colors
        ${drag ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}
        ${disabled ? 'opacity-60 pointer-events-none' : 'cursor-pointer'}
      `}
    >
      <input
        type="file"
        accept={accept}
        onChange={onInputChange}
        disabled={disabled}
        className="hidden"
        id="payroll-file-input"
      />
      <label htmlFor="payroll-file-input" className="cursor-pointer block">
        <span className="text-gray-600 block text-lg">
          {selectedName ?? 'Drop CSV here or click to browse'}
        </span>
        <span className="text-gray-400 text-sm mt-2 block">CSV payroll export</span>
      </label>
    </div>
  );
}
