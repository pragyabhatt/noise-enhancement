// src/pages/Login.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const [error, setError] = React.useState<string>('');
  const [user, setUser] = React.useState({ username: '', password: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Simple POST to /auth/login (backend already implements JWT login)
      const resp = await axios.post('/api/auth/login', new URLSearchParams(user as any).toString(), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
      if (resp.data.access_token) {
        localStorage.setItem('token', resp.data.access_token);
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Login failed');
    }
  };

  return (
    <div className="page login-page">
      <h2>Login</h2>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit} className="login-form">
        <input
          type="text"
          placeholder="Username"
          value={user.username}
          onChange={(e) => setUser({ ...user, username: e.target.value })}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={user.password}
          onChange={(e) => setUser({ ...user, password: e.target.value })}
          required
        />
        <button type="submit">Sign In</button>
      </form>
    </div>
  );
};

export default Login;
