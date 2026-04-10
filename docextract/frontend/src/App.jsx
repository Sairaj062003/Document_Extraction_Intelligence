import { useState } from 'react';
import UploadZone from './components/UploadZone';
import ResultsPanel from './components/ResultsPanel';

export default function App() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  return (
    <>
      {/* Header */}
      <header className="header">
        <div className="container header-inner">
          <div className="logo">
            <div className="logo-icon">⚡</div>
            <span className="logo-text">DocExtract</span>
          </div>
          <span className="header-badge">3 Extractors · Parallel</span>
        </div>
      </header>

      {/* Main */}
      <main>
        <div className="container">

          {/* Hero */}
          <section className="hero">
            <div className="hero-eyebrow">
              <span>✦</span> AI-Powered Document Extraction
            </div>
            <h1 className="hero-title">
              Extract text with <span>three AI models</span> simultaneously
            </h1>
            <p className="hero-sub">
              Upload any document and get parallel results from PaddleOCR,
              LlamaParse, and Gemini Vision — side by side, in seconds.
            </p>
          </section>

          {/* Upload */}
          <UploadZone
            onResults={setResults}
            onLoading={setLoading}
          />

          {/* Divider */}
          {(results || loading) && <div className="divider" />}

          {/* Results */}
          <ResultsPanel results={results} loading={loading} />

        </div>
      </main>
    </>
  );
}
