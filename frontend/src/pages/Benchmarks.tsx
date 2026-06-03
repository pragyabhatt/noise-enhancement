// src/pages/Benchmarks.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';

const Benchmarks: React.FC = () => {
  const navigate = useNavigate();
  return (
    <div className="page benchmarks-page">
      <h2>Benchmarks</h2>
      <p>This page will display benchmark results (e.g., processing speed, model latency).</p>
      {/* Placeholder for future chart components */}
    </div>
  );
};

export default Benchmarks;
