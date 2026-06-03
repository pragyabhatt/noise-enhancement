import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import WaveSurfer from 'wavesurfer.js';

const ProcessFile: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [audioBase64, setAudioBase64] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const originalWave = useRef<WaveSurfer | null>(null);
  const enhancedWave = useRef<WaveSurfer | null>(null);
  const originalContainer = useRef<HTMLDivElement>(null);
  const enhancedContainer = useRef<HTMLDivElement>(null);

  // Initialize WaveSurfer instances
  useEffect(() => {
    if (originalContainer.current) {
      originalWave.current = WaveSurfer.create({
        container: originalContainer.current,
        waveColor: '#00e5ff',
        progressColor: '#10b981',
        height: 80,
        responsive: true,
        backend: 'WebAudio'
      });
    }
    if (enhancedContainer.current) {
      enhancedWave.current = WaveSurfer.create({
        container: enhancedContainer.current,
        waveColor: '#ffb300',
        progressColor: '#00e5ff',
        height: 80,
        responsive: true,
        backend: 'WebAudio'
      });
    }
    return () => {
      originalWave.current?.destroy();
      enhancedWave.current?.destroy();
    };
  }, []);

  // Load waves when audio data arrives
  useEffect(() => {
    if (audioBase64 && originalWave.current && enhancedWave.current) {
      const rawUrl = `data:audio/wav;base64,${audioBase64}`;
      // Load original (noisy) from the file object
      const reader = new FileReader();
      reader.onload = () => {
        const noisyUrl = reader.result as string;
        originalWave.current?.load(noisyUrl);
        enhancedWave.current?.load(rawUrl);
      };
      reader.readAsDataURL(file as Blob);
    }
  }, [audioBase64, file]);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type === 'audio/wav') {
      setFile(dropped);
    } else {
      setError('Please drop a .wav audio file');
    }
  };

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
        headers: { 'Content-Type': 'multipart/form-data', Authorization: `Bearer ${token}` }
      });
      const { job_id, metrics, audio_base64 } = resp.data;
      setMetrics(metrics);
      setAudioBase64(audio_base64);
      // Store for later evaluation page if needed
      sessionStorage.setItem('lastJob', JSON.stringify({ job_id, metrics, audio_base64 }));
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Processing failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page process-page space-y-6">
      <h2 className="text-2xl font-bold text-[#e0e7ff]">Process File</h2>
      {error && <div className="text-red-400">{error}</div>}
      <form onSubmit={handleSubmit} className="flex flex-col items-center" onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
        <div className="border-2 border-dashed border-[#00e5ff] rounded-lg p-8 text-center cursor-pointer w-full max-w-md" onClick={() => document.getElementById('fileInput')?.click()}>
          {file ? (
            <p className="text-[#00e5ff]">{file.name}</p>
          ) : (
            <p className="text-gray-400">Drag & drop a .wav file here, or click to select</p>
          )}
          <input id="fileInput" type="file" accept=".wav" style={{ display: 'none' }} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <button type="submit" disabled={loading || !file} className="mt-4 px-4 py-2 bg-[#00e5ff] text-[#0f172a] rounded hover:bg-[#00c4e0]">
          {loading ? 'Processing…' : 'Upload & Enhance'}
        </button>
      </form>

      {metrics && (
        <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg text-[#e0e7ff]">
          <pre className="whitespace-pre-wrap break-words">{JSON.stringify(metrics, null, 2)}</pre>
        </div>
      )}

      {/* Waveform comparison */}
      {audioBase64 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 className="text-gray-300 mb-2">Noisy (Original)</h3>
            <div ref={originalContainer} className="bg-[#1e293b] rounded-md" />
          </div>
          <div>
            <h3 className="text-gray-300 mb-2">Enhanced</h3>
            <div ref={enhancedContainer} className="bg-[#1e293b] rounded-md" />
          </div>
        </div>
      )}
    </div>
  );
};

export default ProcessFile;