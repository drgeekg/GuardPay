/**
 * GuardPay Frontend API Client
 * Dynamically resolves API_BASE so it works on localhost, dev server, and public tunnels (ngrok/localtunnel)
 */

const API_BASE =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
    ? import.meta.env.VITE_API_URL.replace(/\/$/, '')
    : typeof window !== 'undefined' && window.location.port === '5173'
    ? 'http://localhost:8000'
    : '';

const DEFAULT_HEADERS = {
  'ngrok-skip-browser-warning': 'true',
  'Bypass-Tunnel-Reminder': 'true',
};

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`, {
    headers: { ...DEFAULT_HEADERS },
  });
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function fetchAlerts() {
  const res = await fetch(`${API_BASE}/alerts`, {
    headers: { ...DEFAULT_HEADERS },
  });
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchDossier(alertId) {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/dossier`, {
    headers: { ...DEFAULT_HEADERS },
  });
  if (!res.ok) throw new Error(`Failed to fetch dossier for ${alertId}`);
  return res.json();
}

export async function blockSubnet(alertId, actor = 'merchant_demo') {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/actions/block-subnet`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...DEFAULT_HEADERS },
    body: JSON.stringify({ actor, reason_acknowledged: true }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to block subnet');
  }
  return res.json();
}

export async function enable3DS(alertId, actor = 'merchant_demo') {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/actions/enable-3ds`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...DEFAULT_HEADERS },
    body: JSON.stringify({ actor, reason_acknowledged: true }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to enable 3DS');
  }
  return res.json();
}

export async function overrideAlert(alertId, actor = 'merchant_demo') {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...DEFAULT_HEADERS },
    body: JSON.stringify({ actor }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to override alert');
  }
  return res.json();
}

export async function undoAction(actionId, actor = 'merchant_admin') {
  const res = await fetch(`${API_BASE}/actions/${actionId}/undo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...DEFAULT_HEADERS },
    body: JSON.stringify({ actor }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to undo action');
  }
  return res.json();
}

export async function fetchAuditLog() {
  const res = await fetch(`${API_BASE}/audit-log`, {
    headers: { ...DEFAULT_HEADERS },
  });
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

export async function sendTransaction(txn) {
  const res = await fetch(`${API_BASE}/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...DEFAULT_HEADERS },
    body: JSON.stringify(txn),
  });
  if (!res.ok) throw new Error('Failed to ingest transaction');
  return res.json();
}
