// src/pages/ProcessFile.tsx
import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const ProcessFile: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const form = new FormData();
      form.append('file', file);
      const resp = await axios.post('/process/file', form, {
        headers: {
          'Content-Type': 'multipart/form-data',
          Authorization: `Bearer ${token}`,
        },
      });
      // Assume response contains metrics and base64 audio
      const { job_id, metrics, audio_base64 } = resp.data;
      // Store result in sessionStorage for the Evaluation page
      sessionStorage.setItem('lastJob', JSON.stringify({ job_id, metrics, audio_base64 }));
      navigate('/evaluation');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Processing failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page process-page">
      <h2>Process File</h2>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit} className="process-form">
        <input
          type="file"
          accept=".wav"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Processing…' : 'Upload & Enhance'}
        </button>
      </form>
    </div>
  );
};

export default ProcessFile;