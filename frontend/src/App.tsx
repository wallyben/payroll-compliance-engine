import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { ScanProvider } from './context/ScanContext';
import { UploadPage } from './pages/UploadPage';
import { ResultsPage } from './pages/ResultsPage';
import { SummaryPage } from './pages/SummaryPage';

export default function App() {
  return (
    <ScanProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-white text-gray-900">
          <NavBar />
          <main>
            <Routes>
              <Route path="/" element={<UploadPage />} />
              <Route path="/results" element={<ResultsPage />} />
              <Route path="/summary" element={<SummaryPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ScanProvider>
  );
}
