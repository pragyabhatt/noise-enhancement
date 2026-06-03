import React, { useEffect, useState } from 'react';
import { getDashboardData } from '../api/client';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, AreaChart, Area, ResponsiveContainer } from 'recharts';

interface KPIProps {
  title: string;
  value: string | number;
  unit?: string;
}

const KpiCard: React.FC<KPIProps> = ({ title, value, unit }) => (
  <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg text-center text-[#e0e7ff]">
    <h3 className="text-sm font-medium text-gray-400 mb-1">{title}</h3>
    <p className="text-2xl font-bold">{value}{unit && <span className="text-sm ml-1">{unit}</span>}</p>
  </div>
);

const Dashboard: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetch = async () => {
      try {
        const resp = await getDashboardData();
        setData(resp);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Failed to load dashboard');
      }
    };
    fetch();
  }, []);

  if (error) return <div className="text-red-400">{error}</div>;
  if (!data) return <div className="text-gray-400">Loading dashboard…</div>;

  const { kpis, snr_trend, noise_distribution, latency_trend, recent_jobs } = data;

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard title="Processed Files" value={kpis.total_processed} />
        <KpiCard title="Avg SNR ↑" value={kpis.avg_snr_improvement} unit="dB" />
        <KpiCard title="Avg DNSMOS" value={kpis.avg_dnsmos?.toFixed(2)} />
        <KpiCard title="System Health" value={kpis.system_health} />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SNR Trend Line */}
        <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg">
          <h4 className="text-gray-300 mb-2">SNR Trend (Last 7 days)</h4>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={snr_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" domain={['dataMin-5', 'dataMax+5']} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', color: '#e0e7ff' }} />
              <Line type="monotone" dataKey="pre_snr" stroke="#00e5ff" name="Pre‑SNR" dot={false} />
              <Line type="monotone" dataKey="post_snr" stroke="#10b981" name="Post‑SNR" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Noise Distribution Bar */}
        <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg">
          <h4 className="text-gray-300 mb-2">Noise Profile Distribution</h4>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={noise_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="class" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', color: '#e0e7ff' }} />
              <Bar dataKey="count" fill="#ffb300" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Latency Trend Area */}
        <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg lg:col-span-2">
          <h4 className="text-gray-300 mb-2">Processing Latency (ms) – Recent 15 jobs</h4>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={latency_trend}>
              <defs>
                <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#00e5ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="job_id" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', color: '#e0e7ff' }} />
              <Area type="monotone" dataKey="latency_ms" stroke="#00e5ff" fillOpacity={1} fill="url(#colorLatency)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Jobs Table */}
      <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg overflow-x-auto">
        <h4 className="text-gray-300 mb-2">Recent Jobs</h4>
        <table className="w-full text-left text-sm text-[#e0e7ff]">
          <thead className="border-b border-gray-600">
            <tr>
              <th className="p-2">ID</th>
              <th className="p-2">Status</th>
              <th className="p-2">SNR Δ (dB)</th>
              <th className="p-2">Noise</th>
              <th className="p-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {recent_jobs.map((job: any) => (
              <tr key={job.id} className="border-b border-gray-700">
                <td className="p-2">{job.id}</td>
                <td className="p-2 capitalize">{job.status}</td>
                <td className="p-2">{job.snr_improvement?.toFixed(2)}</td>
                <td className="p-2">{job.noise_class}</td>
                <td className="p-2">{new Date(job.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
