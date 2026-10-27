/**
 * Shared API Client Module (Phase 3 Frontend Modularization).
 * Provides centralized HTTP request handling and JWT token injection.
 */

export function getAuthToken() {
  try {
    return window.localStorage.getItem("auth_token");
  } catch {
    return null;
  }
}

export async function apiFetch(path, options = {}) {
  const token = getAuthToken();
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(path, {
    ...options,
    headers,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  return { ok: response.ok, status: response.status, data };
}
