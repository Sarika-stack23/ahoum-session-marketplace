/**
 * Session detail page with booking action.
 *
 * Shows:
 * - Full session information
 * - Current availability (INFORMATIONAL — backend is authoritative)
 * - Booking button with appropriate state
 * - Booking protection info panel
 * - Error handling for all booking failure cases
 */
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest, parseError } from '../api';

export default function SessionDetail() {
  const { id } = useParams();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [bookingResult, setBookingResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`/api/sessions/${id}/`)
      .then(async (res) => {
        if (!res.ok) throw new Error('Session not found');
        setSession(await res.json());
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleBook = async () => {
    if (booking) return;
    setBooking(true);
    setBookingResult(null);

    const idempotencyKey = crypto.randomUUID();

    try {
      const response = await apiRequest(`/bookings/session/${id}/book/`, {
        method: 'POST',
        idempotencyKey,
      });

      if (response.ok) {
        const data = await response.json();
        setBookingResult({ type: 'success', message: 'Booking confirmed!', data });
        // Refresh session data
        const refreshed = await fetch(`/api/sessions/${id}/`);
        if (refreshed.ok) setSession(await refreshed.json());
      } else {
        const err = await parseError(response);
        const messages = {
          SESSION_FULL: 'This session just became full. Another booking completed before your request.',
          DUPLICATE_BOOKING: 'You already have an active booking for this session.',
          SESSION_STARTED: 'This session has already started and cannot be booked.',
          SESSION_NOT_FOUND: 'This session no longer exists.',
          INVALID_TOKEN: 'Your session has expired. Please sign in again.',
          TOKEN_EXPIRED: 'Your session has expired. Please sign in again.',
        };
        setBookingResult({
          type: 'error',
          code: err.code,
          message: messages[err.code] || err.message,
          requestId: err.request_id,
        });
      }
    } catch {
      setBookingResult({
        type: 'error',
        code: 'NETWORK_ERROR',
        message: 'Could not connect to the server. Please try again.',
      });
    } finally {
      setBooking(false);
    }
  };

  if (loading) return <div className="page-center"><div className="spinner" /></div>;
  if (error) return <div className="page-center"><div className="alert alert-error">{error}</div></div>;
  if (!session) return null;

  const isFull = session.remaining_seats === 0;
  const hasStarted = session.has_started;

  return (
    <div className="container">
      <button onClick={() => navigate('/')} className="btn btn-secondary btn-sm" style={{marginBottom: '1rem'}}>
        ← Back to catalog
      </button>

      <div className="session-detail">
        <h1>{session.title}</h1>
        <p className="text-muted">by {session.creator_name}</p>

        {session.description && (
          <div className="section">
            <h3>Description</h3>
            <p>{session.description}</p>
          </div>
        )}

        <div className="section">
          <h3>Details</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Date & Time</span>
              <span className="detail-value">
                {new Date(session.start_time).toLocaleString()}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Capacity</span>
              <span className="detail-value">{session.capacity}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Booked</span>
              <span className="detail-value">{session.booked_count}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Available</span>
              <span className="detail-value">
                {hasStarted ? 'N/A' : session.remaining_seats}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Status</span>
              <span className="detail-value">
                {hasStarted ? (
                  <span className="badge badge-muted">Started</span>
                ) : isFull ? (
                  <span className="badge badge-full">Full</span>
                ) : (
                  <span className="badge badge-available">Open</span>
                )}
              </span>
            </div>
          </div>
        </div>

        {/* Booking action */}
        <div className="section">
          {!isAuthenticated ? (
            <button onClick={() => navigate('/login')} className="btn btn-primary">
              Sign in to Book
            </button>
          ) : hasStarted ? (
            <button disabled className="btn btn-disabled">
              Session Already Started
            </button>
          ) : isFull ? (
            <button disabled className="btn btn-disabled">
              Session Full
            </button>
          ) : (
            <button onClick={handleBook} disabled={booking} className="btn btn-primary">
              {booking ? 'Booking...' : 'Book This Session'}
            </button>
          )}
        </div>

        {/* Booking result feedback */}
        {bookingResult && (
          <div className={`alert alert-${bookingResult.type === 'success' ? 'success' : 'error'}`}>
            <p>{bookingResult.message}</p>
            {bookingResult.requestId && (
              <p className="text-muted text-sm">Request ID: {bookingResult.requestId}</p>
            )}
          </div>
        )}

        {/* Booking Protection Panel */}
        <div className="section protection-panel">
          <h3>Booking Protected</h3>
          <ul className="protection-list">
            <li>✓ Capacity enforced by backend</li>
            <li>✓ Duplicate active bookings prevented</li>
            <li>✓ Session start time enforced</li>
            <li>✓ Concurrent booking protection enabled</li>
          </ul>
          <p className="text-muted text-sm">
            The displayed seat count is informational. Final booking
            validation happens on the backend inside a database-protected
            transaction.
          </p>
        </div>
      </div>
    </div>
  );
}
