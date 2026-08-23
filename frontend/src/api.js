/**
 * GuardPay Frontend API Client
 * Connects directly to backend (http://localhost:8000 or via proxy)
 */

const API_BASE = 'http://localhost:8000';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function fetchAlerts() {
  const res = await fetch(`${API_BASE}/alerts`);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchDossier(alertId) {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/dossier`);
  if (!res.ok) throw new Error(`Failed to fetch dossier for ${alertId}`);
  return res.json();
}

export async function blockSubnet(alertId, actor = 'merchant_demo') {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/actions/block-subnet`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
    headers: { 'Content-Type': 'application/json' },
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
    headers: { 'Content-Type': 'application/json' },
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actor }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to undo action');
  }
  return res.json();
}

export async function fetchAuditLog() {
  const res = await fetch(`${API_BASE}/audit-log`);
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

export async function sendTransaction(txn) {
  const res = await fetch(`${API_BASE}/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(txn),
  });
  if (!res.ok) throw new Error('Failed to ingest transaction');
  return res.json();
}
