import { useState, useEffect } from 'react';
import { apiRequest } from '../api';

export default function BookingIntegrityConsole({ sessionId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
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

  if (loading) return <div className="card loading-state">Loading integrity data...</div>;
  if (error) return <div className="card error-state">{error}</div>;
  if (!data) return null;

  const getExplanation = (eventType) => {
    switch (eventType) {
      case 'BOOKING_REJECTED_CAPACITY':
        return 'Rejected because the session reached capacity. (Concurrency lock caught race condition).';
      case 'BOOKING_REJECTED_DUPLICATE':
        return 'Rejected because this user already has a confirmed booking.';
      case 'BOOKING_REJECTED_STARTED':
        return 'Rejected because the session had already started.';
      case 'BOOKING_CONFIRMED':
        return 'Booking created successfully within capacity.';
      case 'BOOKING_CANCELLED':
        return 'Booking was cancelled by the user.';
      default:
        return 'Recorded booking event.';
    }
  };

  const isPass = data.invariant.status === 'PASS';

  return (
    <div className="integrity-console card fade-in mt-4 border-primary">
      <div className="console-header flex-between mb-3">
        <h2>Booking Integrity: {data.title}</h2>
        <button onClick={onClose} className="btn btn-secondary btn-sm">Close</button>
      </div>

      <div className="console-grid">
        {/* Invariant Status */}
        <div className="console-section">
          <h3>Core Invariant Status</h3>
          <div className={`status-badge ${isPass ? 'badge-success' : 'badge-danger'}`}>
            {data.invariant.name}: {data.invariant.status}
          </div>
          <div className="capacity-summary mt-3">
            <p><strong>Capacity:</strong> {data.capacity}</p>
            <p><strong>Confirmed Bookings:</strong> {data.confirmed_bookings}</p>
            <p><strong>Remaining Seats:</strong> {data.remaining_seats}</p>
          </div>
        </div>

        {/* Concurrency Explanation */}
        <div className="console-section">
          <h3>Concurrency Protection</h3>
          <p className="text-sm">
            The database transaction and row-level locking prevent capacity overselling under the tested concurrent booking scenarios.
          </p>
          <div className="code-block text-xs mt-2" style={{ background: '#1a1a1a', padding: '1rem', borderRadius: '4px', color: '#00ffcc', fontFamily: 'monospace' }}>
            BEGIN TRANSACTION;<br/>
            SELECT * FROM sessions WHERE id = {sessionId} FOR UPDATE;<br/>
            -- Application checks capacity against lock<br/>
            COMMIT;
          </div>
        </div>
      </div>

      {/* Event Timeline */}
      <div className="console-section mt-4">
        <h3>Booking Event Timeline</h3>
        {data.recent_booking_events.length === 0 ? (
          <p className="text-muted text-sm mt-2">No booking events recorded yet.</p>
        ) : (
          <div className="event-timeline mt-3">
            {data.recent_booking_events.map((event, i) => (
              <div key={i} className="timeline-item" style={{ borderLeft: '2px solid #3b82f6', paddingLeft: '1rem', marginBottom: '1rem' }}>
                <div className="timeline-time text-xs text-muted">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </div>
                <div className="timeline-content">
                  <div className="timeline-title" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <strong>{event.event_type}</strong>
                    <span className="badge badge-secondary">{event.username}</span>
                  </div>
                  <div className="timeline-desc text-sm text-muted mt-1">
                    {getExplanation(event.event_type)}
                  </div>
                  <div className="timeline-meta text-xs text-muted mt-1 opacity-70">
                    Req ID: {event.request_id || 'None'}
                    {event.booking_id && ` | Booking #${event.booking_id}`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
