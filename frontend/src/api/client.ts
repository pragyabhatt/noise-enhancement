import axios from 'axios';

const api = axios.create({
  baseURL: '/', // Proxy will forward to FastAPI
  withCredentials: true,
});

export const login = async (username: string, password: string) => {
  const response = await api.post('/auth/login', { username, password });
  return response.data;
};

export const uploadFile = async (file: File, targetSNR: number) => {
  const form = new FormData();
  form.append('file', file);
  form.append('target_snr', targetSNR.toString());
  const response = await api.post('/process/file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getJobStatus = async (jobId: number, download?: boolean) => {
  const params: any = {};
  if (download) params.download = true;
  const response = await api.get(`/process/jobs/${jobId}`, { params });
  return response.data;
};

// Add more API helpers as needed (metrics, eval, audit, admin)
