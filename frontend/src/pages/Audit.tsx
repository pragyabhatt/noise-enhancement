import React, { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import axios from '../api/client';

interface LogEntry {
  id: number;
  user: string;
  action: string;
  timestamp: string;
  details: string;
}

const PAGE_SIZES = [5, 10, 20, 50];

const Audit: React.FC = () => {
  const { user } = useAuth();
  const { ToastContainer, trigger } = useToast();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params: any = { page, limit: pageSize };
      if (search) params.user = search;
      const resp = await axios.get('/admin/audit', { params });
      setLogs(resp.data.items);
      setTotal(resp.data.total);
    } catch (e: any) {
      trigger('Failed to load audit logs', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, search]);

  // Non‑admin users are redirected by PrivateRoute, but guard just in case
  if (user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      {ToastContainer && <ToastContainer />}
      <h2 className="text-2xl font-bold text-[#e0e7ff]">Audit Logs</h2>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <input
          type="text"
          placeholder="Search by username"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 bg-[#2c2c3d] border border-gray-600 rounded text-[#e0e7ff]"
        />
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          className="px-2 py-1 bg-[#2c2c3d] border border-gray-600 rounded text-[#e0e7ff]"
        >
          {PAGE_SIZES.map((size) => (
            <option key={size} value={size}>
              {size} per page
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-left text-[#e0e7ff]">
          <thead className="bg-[#1e293b]">
            <tr>
              <th className="px-4 py-2">ID</th>
              <th className="px-4 py-2">User</th>
              <th className="px-4 py-2">Action</th>
              <th className="px-4 py-2">Timestamp</th>
              <th className="px-4 py-2">Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-gray-700">
                <td className="px-4 py-2">{log.id}</td>
                <td className="px-4 py-2">{log.user}</td>
                <td className="px-4 py-2">{log.action}</td>
                <td className="px-4 py-2">{new Date(log.timestamp).toLocaleString()}</td>
                <td className="px-4 py-2 break-all">{log.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-4">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(p - 1, 1))}
          className="px-3 py-1 bg-[#00e5ff] text-[#0f172a] rounded disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-[#e0e7ff]">
          Page {page} of {totalPages}
        </span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
          className="px-3 py-1 bg-[#00e5ff] text-[#0f172a] rounded disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default Audit;
