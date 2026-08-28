/**
 * Session detail page with booking action.
 *
 * Shows full session information, availability visualization,
 * and booking flow with proper error handling for all cases.
 * Backend remains authoritative for all booking decisions.
 */
import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
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
        setBookingResult({
          type: 'success',
          message: 'Your seat has been reserved.',
          data,
        });
        // Refresh session data
        const refreshed = await fetch(`/api/sessions/${id}/`);
        if (refreshed.ok) setSession(await refreshed.json());
      } else {
        const err = await parseError(response);
        const messages = {
          SESSION_FULL: 'This session is now full. Another booking was confirmed just before yours.',
          DUPLICATE_BOOKING: 'You already have a booking for this session.',
          SESSION_STARTED: 'This session has already started and is no longer accepting bookings.',
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
        message: 'Could not connect to the server. Please check your connection and try again.',
      });
    } finally {
      setBooking(false);
    }
  };

  if (loading) {
    return (
      <div className="container">
        <div className="session-detail">
          <div className="skeleton skeleton-line w-25" />
          <div className="skeleton skeleton-line w-75" style={{ height: 28, marginTop: '1rem' }} />
          <div className="skeleton skeleton-line w-50" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '0.75rem', marginTop: '2rem' }}>
            {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 72 }} />)}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-center">
        <div className="alert alert-error">{error}</div>
        <button className="btn btn-primary" onClick={() => navigate('/')}>
          Back to Browse
        </button>
      </div>
    );
  }

  if (!session) return null;

  const isFull = session.remaining_seats === 0;
  const hasStarted = session.has_started;
  const fillPct = Math.round(((session.capacity - session.remaining_seats) / session.capacity) * 100);

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  };
  const formatTime = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  return (
    <div className="container slide-up">
      <div className="breadcrumb">
        <Link to="/">Browse</Link>
        <span>›</span>
        <span>{session.title}</span>
      </div>

      <div className="session-detail">
        <div className="detail-header">
          <div className="flex items-center gap-2" style={{ gap: '0.75rem', marginBottom: '0.75rem' }}>
            {hasStarted ? (
              <span className="badge badge-started">Started</span>
            ) : isFull ? (
              <span className="badge badge-full">Full</span>
            ) : session.remaining_seats <= Math.ceil(session.capacity * 0.2) ? (
              <span className="badge badge-almost-full">Almost Full</span>
            ) : (
              <span className="badge badge-available">Available</span>
            )}
          </div>
          <h1>{session.title}</h1>
          <p className="creator-line">by {session.creator_name}</p>
        </div>

        {session.description && (
          <div className="section">
            <h3 className="section-title">About</h3>
            <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>{session.description}</p>
          </div>
        )}

        <div className="section">
          <h3 className="section-title">Details</h3>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-label">Date</span>
              <span className="detail-value" style={{ fontSize: '0.9375rem' }}>
                {formatDate(session.start_time)}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Time</span>
              <span className="detail-value" style={{ fontSize: '0.9375rem' }}>
                {formatTime(session.start_time)}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Capacity</span>
              <span className="detail-value">{session.capacity}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Available</span>
              <span className="detail-value">
                {hasStarted ? '—' : session.remaining_seats}
              </span>
            </div>
          </div>
        </div>

        {/* Availability visualization */}
        {!hasStarted && (
          <div className="section">
            <h3 className="section-title">Availability</h3>
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius)', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.8125rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{session.capacity - session.remaining_seats} booked</span>
                <span style={{ color: 'var(--text-secondary)' }}>{session.remaining_seats} remaining</span>
              </div>
              <div className="capacity-bar" style={{ maxWidth: '100%', height: 8 }}>
                <div
                  className={`capacity-fill ${isFull ? 'full' : fillPct >= 80 ? 'high' : fillPct >= 50 ? 'medium' : 'low'}`}
                  style={{ width: `${fillPct}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Booking action */}
        <div className="booking-action">
          {!isAuthenticated ? (
            <>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem', fontSize: '0.875rem' }}>
                Sign in with GitHub to reserve your seat.
              </p>
              <button onClick={() => navigate('/login')} className="btn btn-primary btn-lg">
                Sign in to Book
              </button>
            </>
          ) : hasStarted ? (
            <button disabled className="btn btn-disabled btn-lg">
              Session Already Started
            </button>
          ) : isFull ? (
            <button disabled className="btn btn-disabled btn-lg">
              Session Full — No Seats Available
            </button>
          ) : (
            <button onClick={handleBook} disabled={booking} className="btn btn-primary btn-lg">
              {booking ? (
                <>
                  <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                  Reserving...
                </>
              ) : (
                'Reserve Your Seat'
              )}
            </button>
          )}
        </div>

        {/* Booking result feedback */}
        {bookingResult && (
          <div className={`alert alert-${bookingResult.type === 'success' ? 'success' : 'error'}`}>
            <div>
              <p style={{ fontWeight: 500 }}>{bookingResult.message}</p>
              {bookingResult.requestId && (
                <p className="text-xs mt-1" style={{ opacity: 0.7 }}>Request ID: {bookingResult.requestId}</p>
              )}
              {bookingResult.type === 'success' && (
                <div style={{ marginTop: '0.75rem' }}>
                  <button onClick={() => navigate('/bookings')} className="btn btn-sm btn-secondary">
                    View My Bookings
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Booking Protection Panel */}
        <div className="protection-panel">
          <h3>Booking Protection</h3>
          <ul className="protection-list">
            <li>✓ Capacity enforced by database transaction</li>
            <li>✓ Duplicate bookings prevented</li>
            <li>✓ Session start time validated</li>
            <li>✓ Concurrent booking protection (SELECT FOR UPDATE)</li>
          </ul>
          <p className="text-xs mt-3" style={{ color: 'var(--text-tertiary)' }}>
            Seat counts shown here are informational. Final validation occurs server-side
            within a PostgreSQL transaction using row-level locking.
          </p>
        </div>
      </div>
    </div>
  );
}
