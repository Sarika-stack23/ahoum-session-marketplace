/**
 * API client with automatic token refresh.
 *
 * All API calls go through this module. If a request fails with
 * 401 (expired token), it automatically attempts to refresh the
 * access token and retry the original request ONCE.
 *
 * Never exposes tokens in URLs or logs.
 */

const API_BASE = import.meta.env.VITE_API_URL || '/api';

let accessToken = localStorage.getItem('access_token');
let refreshToken = localStorage.getItem('refresh_token');

// Callback set by AuthContext to handle forced logout
let onAuthFailure = null;

export function setAuthFailureHandler(handler) {
  onAuthFailure = handler;
}

export function setTokens(access, refresh) {
  accessToken = access;
  refreshToken = refresh;
  if (access) {
    localStorage.setItem('access_token', access);
  } else {
    localStorage.removeItem('access_token');
  }
  if (refresh) {
    localStorage.setItem('refresh_token', refresh);
  } else {
    localStorage.removeItem('refresh_token');
  }
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

export function getAccessToken() {
  return accessToken;
}

async function refreshAccessToken() {
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${API_BASE}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const data = await response.json();
    setTokens(data.access, data.refresh);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

/**
 * Make an authenticated API request.
 *
 * @param {string} endpoint - API endpoint (e.g., '/auth/profile/')
 * @param {object} options - fetch options
 * @param {object} options.headers - additional headers
 * @param {string} options.idempotencyKey - Idempotency-Key header
 * @returns {Promise<Response>}
 */
export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  if (options.idempotencyKey) {
    headers['Idempotency-Key'] = options.idempotencyKey;
  }

  let response = await fetch(url, {
    ...options,
    headers,
  });

  // If 401, try refreshing the token once
  if (response.status === 401 && refreshToken) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${accessToken}`;
      response = await fetch(url, { ...options, headers });
    } else {
      if (onAuthFailure) onAuthFailure();
    }
  }

  return response;
}

/**
 * Parse API error response into a friendly object.
 */
export async function parseError(response) {
  try {
    const data = await response.json();
    if (data.error) {
      return data.error;
    }
    return { code: 'UNKNOWN', message: 'An unexpected error occurred.' };
  } catch {
    return { code: 'NETWORK_ERROR', message: 'Could not connect to the server.' };
  }
}
