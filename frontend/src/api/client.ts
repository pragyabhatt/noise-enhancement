import axios from 'axios';

// Create Axios client with /api prefix
export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

// Request interceptor to attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

  // Response interceptor to handle token expiry (401 Unauthorized) and errors
  api.interceptors.response.use(
    (response) => response,
    (error) => {
      // Show toast for any error response
      if (typeof addToastGlobal === 'function') {
        const msg = error?.response?.data?.detail || error.message || 'An error occurred';
        addToastGlobal(msg, 'error');
      }
      if (error.response && error.response.status === 401) {
        // Clear token and redirect to login page
        localStorage.removeItem('token');
        if (!window.location.pathname.endsWith('/login')) {
          window.location.href = '/login';
        }
      }
      return Promise.reject(error);
    }
  );

// Auth login operation
export const login = async (username: string, password: string) => {
  const params = new URLSearchParams();
  params.append('username', username);
  params.append('password', password);
  const response = await api.post('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
};

// Auth logout operation
export const logoutUser = async () => {
  try {
    await api.post('/auth/logout');
  } catch (err) {
    console.error('Logout request failed:', err);
  } finally {
    localStorage.removeItem('token');
    window.location.href = '/login';
  }
};

// Retrieve authenticated user details
export const getMe = async () => {
  const response = await api.get('/auth/me');
  return response.data;
};

// Process File upload
export const uploadFile = async (file: File) => {
  const form = new FormData();
  form.append('file', file);
  const response = await api.post('/process/file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// Retrieve job status or download (handled via process.py)
export const getJobStatus = async (jobId: number) => {
  const response = await api.get(`/process/jobs/${jobId}`);
  return response.data;
};

// List jobs paginated
export const listJobs = async (limit: number = 50, offset: number = 0) => {
  const response = await api.get('/process/jobs', {
    params: { limit, offset }
  });
  return response.data;
};

// Retrieve dashboard KPIs and chart trends
export const getDashboardData = async () => {
  const response = await api.get('/metrics/dashboard');
  return response.data;
};

// Run evaluation on a noisy + clean reference file pair
export const runEvaluation = async (noisyFile: File, refFile: File) => {
  const form = new FormData();
  form.append('noisy_files', noisyFile);
  form.append('ref_files', refFile);
  const response = await api.post('/eval/batch', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

// Run baseline comparisons benchmark
export const runBenchmark = async () => {
  const response = await api.post('/benchmark/run');
  return response.data;
};

// Retrieve detailed audit logs (admin only)
export const fetchAuditLogs = async (limit: number = 100, offset: number = 0) => {
  const response = await api.get('/audit/logs', {
    params: { limit, offset }
  });
  return response.data;
};

// Retrieve system health status (cpu, memory, models loaded)
export const getSystemStatus = async () => {
  const response = await api.get('/admin/status');
  return response.data;
};
