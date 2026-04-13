import { useRef, useState, useCallback } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/extract';

const ALLOWED = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.docx', '.txt'];

const FILE_ICONS = {
  '.pdf':  '📄',
  '.png':  '🖼️',
  '.jpg':  '🖼️',
  '.jpeg': '🖼️',
  '.tiff': '🖼️',
  '.tif':  '🖼️',
  '.docx': '📝',
  '.txt':  '📃',
};

function getExt(name) {
  return name.slice(name.lastIndexOf('.')).toLowerCase();
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

export default function UploadZone({ onResults, onLoading }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const validateAndSet = (f) => {
    if (!f) return;
    const ext = getExt(f.name);
    if (!ALLOWED.includes(ext)) {
      setError(`Unsupported file type "${ext}". Allowed: ${ALLOWED.join(', ')}`);
      return;
    }
    setError(null);
    setFile(f);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    validateAndSet(dropped);
  }, []);

  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);
  const onFileChange = (e) => validateAndSet(e.target.files[0]);

  const handleExtract = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    onLoading(true);
    setError(null);

    try {
      const res = await axios.post(API_URL, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onResults(res.data);
    } catch (err) {
      console.error("API Call Failed to:", API_URL, err);
      const msg = err.response?.data?.detail || err.message || 'Extraction failed';
      setError(msg);
      onResults(null);
    } finally {
      setLoading(false);
      onLoading(false);
    }
  };

  const handleClear = () => {
    setFile(null);
    setError(null);
    onResults(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="upload-section">
      {/* Drop Zone */}
      {!file && (
        <div
          id="upload-dropzone"
          className={`upload-zone glass-card${dragOver ? ' drag-over' : ''}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => inputRef.current?.click()}
        >
          <div className="upload-icon">📂</div>
          <div className="upload-title">
            {dragOver ? 'Drop it here!' : 'Drop your document here'}
          </div>
          <div className="upload-sub">or click to browse from your computer</div>

          <div className="upload-types">
            {ALLOWED.map(t => (
              <span key={t} className="type-chip">{t.toUpperCase().replace('.', '')}</span>
            ))}
          </div>

          <button
            id="btn-browse-files"
            className="btn-upload"
            onClick={e => { e.stopPropagation(); inputRef.current?.click(); }}
          >
            <span>📁</span> Browse Files
          </button>

          <input
            ref={inputRef}
            type="file"
            accept={ALLOWED.join(',')}
            onChange={onFileChange}
            id="file-input"
          />
        </div>
      )}

      {/* File Preview */}
      {file && (
        <div className="file-preview glass-card fade-in">
          <div className="file-preview-icon">
            {FILE_ICONS[getExt(file.name)] ?? '📄'}
          </div>
          <div className="file-preview-info">
            <div className="file-preview-name" title={file.name}>{file.name}</div>
            <div className="file-preview-size">
              {formatSize(file.size)} · {getExt(file.name).toUpperCase().replace('.', '')}
            </div>
          </div>

          <button
            id="btn-extract"
            className="btn-extract"
            onClick={handleExtract}
            disabled={loading}
          >
            {loading ? (
              <><span className="spinner">⏳</span> Extracting…</>
            ) : (
              <><span>⚡</span> Extract</>
            )}
          </button>

          <button
            id="btn-clear"
            className="btn-clear"
            onClick={handleClear}
            title="Remove file"
          >✕</button>
        </div>
      )}

      {/* Loading bar */}
      {loading && (
        <div className="progress-bar">
          <div className="progress-fill" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-msg fade-in" style={{ marginTop: '12px' }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}
