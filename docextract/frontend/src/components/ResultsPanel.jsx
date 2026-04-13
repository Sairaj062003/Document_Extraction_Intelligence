import { useState } from 'react';

const MODEL_META = {
  paddleocr: {
    label: 'PaddleOCR',
    sub: 'Local · No API key',
    icon: '🚀',
    iconClass: 'paddle',
  },
  llamaparse: {
    label: 'LlamaParse',
    sub: 'LlamaCloud · Markdown-aware',
    icon: '🦙',
    iconClass: 'llama',
  },
  gemini: {
    label: 'Gemini Vision',
    sub: 'Auto-selecting best model...',
    icon: '✨',
    iconClass: 'gemini',
  },
  pymupdf4llm: {
    label: 'PyMuPDF4LLM',
    sub: 'Hybrid OCR · Layout-aware',
    icon: '📄',
    iconClass: 'pymupdf',
  },
  mineru_qwen: {
    label: 'MinerU + Qwen',
    sub: 'Local · Offline · AI-refined',
    icon: '🧠',
    iconClass: 'mineru',
  },
};

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  return (
    <button
      className={`btn-copy${copied ? ' copied' : ''}`}
      onClick={handleCopy}
      title={copied ? 'Copied!' : 'Copy text'}
    >
      {copied ? '✓' : '⎘'}
    </button>
  );
}

function SkeletonCard({ modelKey }) {
  const meta = MODEL_META[modelKey];
  return (
    <div className="result-card">
      <div className="card-header">
        <div className="card-model-info">
          <div className={`model-icon ${meta.iconClass}`}>{meta.icon}</div>
          <div>
            <div className="model-name">{meta.label}</div>
            <div className="model-sub">{meta.sub}</div>
          </div>
        </div>
        <span className="status-badge loading">Processing</span>
      </div>
      <div className="card-body">
        {[90, 75, 85, 60, 80].map((w, i) => (
          <div key={i} className="skeleton skeleton-line" style={{ width: `${w}%` }} />
        ))}
      </div>
    </div>
  );
}

function ResultCard({ modelKey, data }) {
  const meta = MODEL_META[modelKey];
  const hasText = data?.text && data.text.trim().length > 0;
  const hasError = !!data?.error;
  const status = hasText ? 'success' : hasError ? 'error' : 'error';

  const modelUsed = data?.model_used;
  const subLabel = modelKey === 'gemini' && modelUsed
    ? modelUsed
    : meta.sub;

  return (
    <div className="result-card">
      {/* Header */}
      <div className="card-header">
        <div className="card-model-info">
          <div className={`model-icon ${meta.iconClass}`}>{meta.icon}</div>
          <div>
            <div className="model-name">{meta.label}</div>
            <div className="model-sub" title={subLabel}>
              {subLabel.length > 32 ? subLabel.slice(0, 32) + '…' : subLabel}
            </div>
          </div>
        </div>
        <div className="card-actions">
          {hasText && <CopyButton text={data.text} />}
          <span className={`status-badge ${status}`}>
            {status === 'success' ? 'Success' : 'Failed'}
          </span>
        </div>
      </div>

      {/* Metrics */}
      {(data?.processing_time_ms !== undefined || data?.pages) && (
        <div className="card-metrics">
          {data.pages > 0 && (
            <div className="metric">
              📄 <strong>{data.pages}</strong> {data.pages === 1 ? 'page' : 'pages'}
            </div>
          )}
          {data.processing_time_ms !== undefined && (
            <div className="metric">
              ⏱ <strong>{(data.processing_time_ms / 1000).toFixed(2)}s</strong>
            </div>
          )}
          {hasText && (
            <div className="metric">
              🔤 <strong>{data.text.trim().split(/\s+/).length}</strong> words
            </div>
          )}
          {data.note && (
            <div className="metric" title={data.note}>
              ℹ️ <strong style={{ fontSize: '0.65rem' }}>{data.note.slice(0, 28)}{data.note.length > 28 ? '…' : ''}</strong>
            </div>
          )}
        </div>
      )}

      {/* Body */}
      <div className="card-body">
        {hasError && (
          <div className="error-msg">⚠️ {data.error}</div>
        )}
        {hasText && (
          <pre className="extracted-text">{data.text}</pre>
        )}
        {!hasText && !hasError && (
          <div className="empty-state">
            <span className="empty-icon">🔍</span>
            No text extracted
          </div>
        )}
      </div>
    </div>
  );
}

export default function ResultsPanel({ results, loading }) {
  if (!results && !loading) return null;

  const modelKeys = ['paddleocr', 'llamaparse', 'gemini', 'pymupdf4llm', 'mineru_qwen'];

  return (
    <div className="results-section fade-in">
      <div className="results-header">
        <div className="results-title">
          <span>📊</span> Extraction Results
          {results?.filename && (
            <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              — {results.filename}
            </span>
          )}
        </div>
        {results && (
          <div className="results-meta">
            File ID: <code style={{ color: 'var(--accent-primary)' }}>{results.file_id?.slice(0, 12)}…</code>
          </div>
        )}
      </div>

      <div className="results-grid">
        {modelKeys.map(key =>
          loading
            ? <SkeletonCard key={key} modelKey={key} />
            : <ResultCard key={key} modelKey={key} data={results?.results?.[key]} />
        )}
      </div>
    </div>
  );
}
