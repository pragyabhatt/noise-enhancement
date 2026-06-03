import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import ProcessFile from './pages/ProcessFile';
import Evaluation from './pages/Evaluation';
import Benchmarks from './pages/Benchmarks';
import Dashboard from './pages/Dashboard';
import Audit from './pages/Audit';
import Layout from './components/Layout';
import { AuthProvider, useAuth } from './hooks/useAuth';

// Private route with optional role requirement
const PrivateRoute: React.FC<{ children: React.ReactNode; requiredRole?: string }> = ({ children, requiredRole }) => {
  const token = localStorage.getItem('token');
  const { user } = useAuth();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (requiredRole && user?.role !== requiredRole) {
    // redirect non‑admin users to dashboard
    return <Navigate to="/dashboard" replace />;
  }
  return <Layout>{children}</Layout>;
};

const App: React.FC = () => {
  return (
    <AuthProvider>
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
              <PrivateRoute requiredRole="admin">
                <Audit />
              </PrivateRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
};

export default App;
