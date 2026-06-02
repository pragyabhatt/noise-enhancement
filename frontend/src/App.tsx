import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import ProcessFile from './pages/ProcessFile';
import Evaluation from './pages/Evaluation';
import Benchmarks from './pages/Benchmarks';
import Dashboard from './pages/Dashboard';
import Audit from './pages/Audit';

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/process" element={<ProcessFile />} />
        <Route path="/evaluation" element={<Evaluation />} />
        <Route path="/benchmarks" element={<Benchmarks />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>
    </Router>
  );
};

export default App;
