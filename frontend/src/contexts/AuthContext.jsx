/**
 * Authentication context — manages auth state, login, logout.
 *
 * State is derived from JWT tokens stored in localStorage.
 * The backend is authoritative — the frontend auth state is
 * for UX only (showing/hiding UI elements).
 */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { setTokens, clearTokens, setAuthFailureHandler, apiRequest } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) {
      // Best-effort logout on backend
      fetch('/api/auth/logout/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      }).catch(() => {});
    }
    clearTokens();
    setUser(null);
  }, []);

  // Register auth failure handler for automatic logout on token expiry
  useEffect(() => {
    setAuthFailureHandler(logout);
  }, [logout]);

  // Check for existing session on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      apiRequest('/auth/profile/')
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            setUser(data);
          } else {
            clearTokens();
          }
        })
        .catch(() => clearTokens())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const loginWithGitHub = useCallback(() => {
    const clientId = import.meta.env.VITE_GITHUB_CLIENT_ID;
    if (!clientId) {
      console.error('VITE_GITHUB_CLIENT_ID not configured');
      return;
    }
    const redirectUri = `${window.location.origin}/auth/callback`;
    const scope = 'user:email';
    const state = crypto.randomUUID();
    sessionStorage.setItem('oauth_state', state);
    window.location.href =
      `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${scope}&state=${state}`;
  }, []);

  const handleOAuthCallback = useCallback(async (code, state) => {
    const savedState = sessionStorage.getItem('oauth_state');
    sessionStorage.removeItem('oauth_state');

    if (state !== savedState) {
      return { error: 'OAUTH_FAILED', message: 'OAuth state mismatch. Please try again.' };
    }

    try {
      const response = await fetch('/api/auth/github/callback/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });

      const data = await response.json();

      if (!response.ok) {
        return data.error || { code: 'OAUTH_FAILED', message: 'Authentication failed.' };
      }

      setTokens(data.access, data.refresh);
      setUser(data.user);
      return null; // No error
    } catch {
      return { code: 'NETWORK_ERROR', message: 'Could not connect to the server.' };
    }
  }, []);

  const updateProfile = useCallback(async (updates) => {
    const response = await apiRequest('/auth/profile/', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
    if (response.ok) {
      const data = await response.json();
      setUser(data);
      return { success: true };
    }
    const errorData = await response.json();
    return { error: errorData.error || { message: 'Update failed.' } };
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      isAuthenticated: !!user,
      isCreator: user?.role === 'CREATOR',
      loginWithGitHub,
      handleOAuthCallback,
      logout,
      updateProfile,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
