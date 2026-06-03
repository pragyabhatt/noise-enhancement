import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import ProcessFile from './pages/ProcessFile';
import Evaluation from './pages/Evaluation';
import Benchmarks from './pages/Benchmarks';
import Dashboard from './pages/Dashboard';
import Audit from './pages/Audit';
import Layout from './components/Layout';

// Simple private route wrapper
const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? <Layout>{children}</Layout> : <Navigate to="/login" replace />;
};

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/process"
          element={
            <PrivateRoute>
              <ProcessFile />
            </PrivateRoute>
          }
        />
        <Route
          path="/evaluation"
          element={
            <PrivateRoute>
              <Evaluation />
            </PrivateRoute>
          }
        />
        <Route
          path="/benchmarks"
          element={
            <PrivateRoute>
              <Benchmarks />
            </PrivateRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
          }
        />
        <Route
          path="/audit"
          element={
            <PrivateRoute>
              <Audit />
            </PrivateRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  );
};

export default App;
