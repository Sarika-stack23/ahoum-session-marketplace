/**
 * Booking Integrity Console — Engineering observability panel.
 *
 * Displays real-time booking integrity data from the backend:
 * - Core invariant status (confirmed_bookings ≤ capacity)
 * - Capacity visualization
 * - Concurrency protection explanation
 * - Real BookingEvent timeline
 *
 * All data comes from the /api/sessions/:id/integrity/ endpoint.
 * No data is fabricated or hardcoded.
 */
import { useState, useEffect } from 'react';
import { apiRequest } from '../api';

export default function BookingIntegrityConsole({ sessionId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiRequest(`/sessions/${sessionId}/integrity/`)
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error?.message || 'Failed to load integrity data');
        }
        setData(await res.json());
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) {
    return (
      <div className="integrity-console fade-in" style={{ marginTop: '2rem' }}>
        <div className="console-header">
          <h2>Loading integrity data...</h2>
          <button onClick={onClose} className="btn btn-ghost btn-sm">Close</button>
        </div>
        <div className="console-body">
          <div className="skeleton" style={{ height: 120 }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="integrity-console fade-in" style={{ marginTop: '2rem' }}>
        <div className="console-header">
          <h2>Integrity Console</h2>
          <button onClick={onClose} className="btn btn-ghost btn-sm">Close</button>
        </div>
        <div className="console-body">
          <div className="alert alert-error">{error}</div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const isPass = data.invariant.status === 'PASS';

  const getEventDot = (type) => {
    if (type === 'BOOKING_CONFIRMED') return 'confirmed';
    if (type === 'BOOKING_CANCELLED') return 'cancelled';
    return 'rejected';
  };

  const getEventLabel = (type) => {
    switch (type) {
      case 'BOOKING_CONFIRMED': return 'Confirmed';
      case 'BOOKING_REJECTED_CAPACITY': return 'Rejected — Capacity';
      case 'BOOKING_REJECTED_DUPLICATE': return 'Rejected — Duplicate';
      case 'BOOKING_REJECTED_STARTED': return 'Rejected — Started';
      case 'BOOKING_CANCELLED': return 'Cancelled';
      default: return type;
    }
  };

  const getEventDesc = (type) => {
    switch (type) {
      case 'BOOKING_CONFIRMED': return 'Booking created within capacity limit.';
      case 'BOOKING_REJECTED_CAPACITY': return 'Rejected by row-level lock — session at capacity.';
      case 'BOOKING_REJECTED_DUPLICATE': return 'Rejected — user already has a confirmed booking.';
      case 'BOOKING_REJECTED_STARTED': return 'Rejected — session has already started.';
      case 'BOOKING_CANCELLED': return 'Booking was cancelled.';
      default: return 'Recorded booking event.';
    }
  };

  return (
    <div className="integrity-console slide-up">
      <div className="console-header">
        <div>
          <div className="console-label">Booking Integrity</div>
          <h2>{data.title}</h2>
        </div>
        <button onClick={onClose} className="btn btn-ghost btn-sm">✕ Close</button>
      </div>

      <div className="console-body">
        <div className="console-grid">
          {/* Invariant Status */}
          <div className="console-section">
            <h3>Invariant</h3>
            <div className={`invariant-box ${isPass ? 'invariant-pass' : 'invariant-fail'}`}>
              <span className="invariant-icon">{isPass ? '✓' : '✕'}</span>
              <span className="invariant-text">
                confirmed_bookings ≤ capacity → {data.invariant.status}
              </span>
            </div>
            <div className="capacity-display">
              <span className="capacity-big">{data.confirmed_bookings}</span>
              <span className="capacity-sep">/</span>
              <span className="capacity-total">{data.capacity}</span>
            </div>
            <div className="capacity-label">confirmed / capacity</div>
            <div style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              {data.remaining_seats} seat{data.remaining_seats !== 1 ? 's' : ''} remaining
            </div>
          </div>

          {/* Concurrency Protection */}
          <div className="console-section">
            <h3>Transaction Pipeline</h3>
            <div className="pipeline">
              <span className="pipeline-step">BEGIN</span>
              <span className="pipeline-arrow">→</span>
              <span className="pipeline-step">SELECT FOR UPDATE</span>
              <span className="pipeline-arrow">→</span>
              <span className="pipeline-step">Validate</span>
              <span className="pipeline-arrow">→</span>
              <span className="pipeline-step">INSERT</span>
              <span className="pipeline-arrow">→</span>
              <span className="pipeline-step">COMMIT</span>
            </div>
            <div className="sql-block" style={{ marginTop: '1rem' }}>
              <span className="sql-keyword">SELECT</span> * <span className="sql-keyword">FROM</span> sessions<br/>
              <span className="sql-keyword">WHERE</span> id = {sessionId} <span className="sql-keyword">FOR UPDATE</span>;<br/>
              <span className="sql-comment">-- Row locked until COMMIT</span><br/>
              <span className="sql-comment">-- Other transactions wait here</span>
            </div>
          </div>
        </div>

        {/* Event Timeline */}
        <div style={{ marginTop: '1rem' }}>
          <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>
            Event Timeline
            <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: '0.5rem', color: 'var(--text-tertiary)' }}>
              (read-only)
            </span>
          </h3>
          {data.recent_booking_events.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem 1rem' }}>
              <p>No booking events recorded yet.</p>
            </div>
          ) : (
            <div className="event-timeline">
              {data.recent_booking_events.map((event, i) => (
                <div key={i} className="timeline-item">
                  <div className={`timeline-dot ${getEventDot(event.event_type)}`} />
                  <div className="timeline-content">
                    <div className="timeline-event-type">
                      {getEventLabel(event.event_type)}
                    </div>
                    <div className="timeline-desc">
                      {getEventDesc(event.event_type)}
                    </div>
                    <div className="timeline-meta">
                      <span>
                        {new Date(event.timestamp).toLocaleString('en-US', {
                          month: 'short', day: 'numeric',
                          hour: 'numeric', minute: '2-digit',
                        })}
                      </span>
                      {event.request_id && event.request_id !== 'None' && (
                        <code title={event.request_id}>
                          req:{event.request_id.slice(0, 12)}
                        </code>
                      )}
                      {event.booking_id && (
                        <span>booking #{event.booking_id}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
