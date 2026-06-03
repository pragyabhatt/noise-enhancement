import React, { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import axios from '../api/client';

interface SystemStatus {
  uptime: string;
  cpu_usage: number;
  memory_usage: number;
  models_loaded: string[];
}

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const location = useLocation();

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await axios.get('/admin/status');
        setStatus(res.data);
        // Persist model list for Benchmarks page
        if (res.data.models_loaded) {
          localStorage.setItem('models', JSON.stringify(res.data.models_loaded));
        }
      } catch (e) {
        console.error('Failed to fetch system status', e);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const navLinkClass = (path: string) =>
    location.pathname.startsWith(path)
      ? 'nav-link active text-cyan-400'
      : 'nav-link text-gray-300 hover:text-cyan-300';

  return (
    <div className="flex min-h-screen bg-[#0f172a] text-[#e0e7ff] font-inter">
      {/* Hamburger button for mobile */}
      <button
        className="md:hidden absolute top-4 left-4 text-cyan-400 focus:outline-none"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle navigation"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <aside
        className={`w-64 bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 flex flex-col transition-transform duration-300 md:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:static`}
      >
        <h2 className="text-xl font-bold text-cyan-400 mb-6 text-center">DEAL Dashboard</h2>
        <nav className="flex flex-col space-y-3">
          <NavLink to="/dashboard" className={() => navLinkClass('/dashboard')}>Dashboard</NavLink>
          <NavLink to="/process" className={() => navLinkClass('/process')}>Process File</NavLink>
          <NavLink to="/evaluation" className={() => navLinkClass('/evaluation')}>Evaluation</NavLink>
          <NavLink to="/benchmarks" className={() => navLinkClass('/benchmarks')}>Benchmarks</NavLink>
          <NavLink to="/audit" className={() => navLinkClass('/audit')}>Audit Log</NavLink>
        </nav>
        <div className="mt-auto pt-4 border-t border-gray-600">
          {status ? (
            <div className="text-sm">
              <div className="flex justify-between"><span>Uptime:</span><span>{status.uptime}</span></div>
              <div className="flex justify-between"><span>CPU:</span><span>{status.cpu_usage}%</span></div>
              <div className="flex justify-between"><span>Mem:</span><span>{status.memory_usage}%</span></div>
              <div className="mt-2">
                <span className="block mb-1">Models:</span>
                <ul className="list-disc list-inside text-xs">
                  {status.models_loaded.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <span className="text-gray-500">Loading status...</span>
          )}
        </div>
      </aside>
      <main className="flex-1 p-6 overflow-auto">
        {children}
      </main>
    </div>
  );
};

export default Layout;
