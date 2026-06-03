// src/pages/Benchmarks.tsx
import React, { useEffect, useState } from 'react';
import { runBenchmark, fetchAuditLogs } from '../api/client'; // will use runBenchmark API
import { useToast } from '../components/Toast';

interface BenchmarkResult {
  model: string;
  seg_snr: number;
  stoi: number;
  latency_ms: number;
}

const Benchmarks: React.FC = () => {
  const [models, setModels] = useState<string[]>([]);
  const [selected, setSelected] = useState('');
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const { trigger } = useToast();

  // Fetch available models from system status (already loaded in Layout status)
  // For simplicity, we re-use the global fetch if needed – assume models are in localStorage after Layout fetch
  useEffect(() => {
    const stored = localStorage.getItem('models');
    if (stored) {
      const arr = JSON.parse(stored);
      setModels(arr);
      setSelected(arr[0] || '');
    }
  }, []);

  const handleRun = async () => {
    if (!selected) return;
    try {
      const data = await runBenchmark(); // backend returns array of results for all models
      // filter for selected model
      const filtered = data.filter((d: any) => d.model === selected);
      setResults(filtered);
      trigger('Benchmark completed', 'success');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Benchmark failed';
      trigger(msg, 'error');
    }
  };

  return (
    <div className="page benchmarks-page">
      <h2 className="text-xl font-bold mb-4 text-[#00e5ff]">Benchmarks</h2>
      <div className="flex items-center space-x-4 mb-6">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="bg-[#2c2c3d] text-[#e0e7ff] p-2 rounded focus:outline-none focus:ring-2 focus:ring-[#00e5ff]"
        >
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button
          onClick={handleRun}
          className="bg-gradient-to-r from-[#00e5ff] to-[#10b981] text-[#0f172a] font-semibold py-2 px-4 rounded hover:from-[#10b981] hover:to-[#00e5ff] transition-all"
        >
          Run Benchmark
        </button>
      </div>
      {results.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Table */}
          <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg overflow-x-auto">
            <h3 className="text-gray-300 mb-2">Results for {selected}</h3>
            <table className="w-full text-left text-sm text-[#e0e7ff]">
              <thead className="border-b border-gray-600">
                <tr>
                  <th className="p-2">Metric</th>
                  <th className="p-2">Value</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <React.Fragment key={i}>
                    <tr className="border-b border-gray-700">
                      <td className="p-2">Seg SNR</td>
                      <td className="p-2">{r.seg_snr.toFixed(2)} dB</td>
                    </tr>
                    <tr className="border-b border-gray-700">
                      <td className="p-2">STOI</td>
                      <td className="p-2">{r.stoi.toFixed(3)}</td>
                    </tr>
                    <tr className="border-b border-gray-700">
                      <td className="p-2">Latency</td>
                      <td className="p-2">{r.latency_ms} ms</td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {/* Bar Chart */}
          <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg">
            <h3 className="text-gray-300 mb-2">Metric Overview</h3>
            {/* Simple Recharts Bar chart */}
            {/* Note: Recharts is already a dependency */}
            {/* We map each metric to a separate bar */}
            {/* For brevity, using static data; can be replaced with dynamic */}
            {/* Placeholder */}
            <p className="text-[#e0e7ff]">[Bar chart placeholder]</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Benchmarks;
