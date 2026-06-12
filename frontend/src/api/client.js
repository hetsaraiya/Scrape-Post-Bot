const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (res.status === 204) return null;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    throw new ApiError(
      data?.detail || `Request failed: ${res.status}`,
      res.status,
      data?.detail,
    );
  }
  return data;
}

export const api = {
  health: () => request('/health'),

  listSources: () => request('/api/v1/sources'),
  getSource: (id) => request(`/api/v1/sources/${id}`),
  createSource: (body) => request('/api/v1/sources', { method: 'POST', body }),
  updateSource: (id, body) => request(`/api/v1/sources/${id}`, { method: 'PUT', body }),
  deleteSource: (id) => request(`/api/v1/sources/${id}`, { method: 'DELETE' }),
  pollSource: (id) => request(`/api/v1/sources/${id}/poll`, { method: 'POST' }),

  listDrafts: (limit = 50, offset = 0) =>
    request(`/api/v1/drafts?limit=${limit}&offset=${offset}`),
  getDraft: (id) => request(`/api/v1/drafts/${id}`),

  pipelineStatus: () => request('/api/v1/pipeline/status'),
  pipelineMetrics: () => request('/api/v1/pipeline/metrics'),
  pipelineRun: () => request('/api/v1/pipeline/run', { method: 'POST' }),
  pipelineMetricsReset: () =>
    request('/api/v1/pipeline/metrics/reset', { method: 'POST' }),
};

export { ApiError };

