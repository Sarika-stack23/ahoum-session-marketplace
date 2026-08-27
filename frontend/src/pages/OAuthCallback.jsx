/**
 * OAuth callback handler.
 *
 * Handles:
 * - Successful code exchange
 * - User cancellation (no code, error=access_denied)
 * - OAuth failure (error in query params)
 * - Network failure
 */
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const [error, setError] = useState(null);
  const { handleOAuthCallback } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const oauthError = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');

    // Handle OAuth cancellation
    if (oauthError === 'access_denied') {
      setError({
        code: 'OAUTH_CANCELLED',
        message: 'Sign-in was cancelled. You can try again.',
      });
      return;
    }

    // Handle other OAuth errors
    if (oauthError) {
      setError({
        code: 'OAUTH_FAILED',
        message: errorDescription || "We couldn't complete sign-in. Please try again.",
      });
      return;
    }

    // No code received
    if (!code) {
      setError({
        code: 'OAUTH_FAILED',
        message: 'No authorization code received.',
      });
      return;
    }

    // Exchange code for tokens
    handleOAuthCallback(code, state).then((err) => {
      if (err) {
        setError(err);
      } else {
        navigate('/');
      }
    });
  }, [searchParams, handleOAuthCallback, navigate]);

  if (error) {
    return (
      <div className="page-center">
        <div className="card">
          <div className="alert alert-error">
            <h2>{error.code === 'OAUTH_CANCELLED' ? 'Sign-in Cancelled' : 'Sign-in Failed'}</h2>
            <p>{error.message}</p>
          </div>
          <button onClick={() => navigate('/login')} className="btn btn-primary">
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-center">
      <div className="card">
        <div className="spinner" />
        <p>Completing sign-in...</p>
      </div>
    </div>
  );
}
