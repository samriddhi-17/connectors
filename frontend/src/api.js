function runtimeConfig() {
  return (typeof window !== 'undefined' && window.CONNECTS_CONFIG) || {};
}

export function apiBase() {
  return (runtimeConfig().apiBase || import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');
}

export function grafanaUrl() {
  return runtimeConfig().grafanaUrl || import.meta.env.VITE_GRAFANA_URL || 'http://localhost:3000';
}

async function request(path, options = {}) {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {
      // keep the HTTP status fallback
    }
    throw new Error(detail);
  }
  return res.json();
}

export function fetchHealth() {
  return request('/healthz');
}

export function fetchConnectors() {
  return request('/api/connectors');
}

export function runQuery(name, operation, payload) {
  return request(`/api/query/${encodeURIComponent(name)}`, {
    method: 'POST',
    body: JSON.stringify({ operation, payload }),
  });
}

export function alertFileList() {
  return request('/api/v1/alerts');
}