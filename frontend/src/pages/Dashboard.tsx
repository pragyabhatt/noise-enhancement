// src/pages/Dashboard.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  return (
    <div className="page dashboard-page">
      <h2>Dashboard</h2>
      <p>Overview of recent jobs, KPI trends, and system status.</p>
      {/* Future: charts (recharts) and status badges */}
    </div>
  );
};

export default Dashboard;
