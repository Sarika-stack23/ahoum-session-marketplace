/**
 * Creator Dashboard with session management and reliability panel.
 *
 * Shows creator's sessions with real statistics, booking counts,
 * and a reliability panel showing active backend protections.
 */
import { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../api';
import BookingIntegrityConsole from '../components/BookingIntegrityConsole';

export default function CreatorDashboard() {
  const { isAuthenticated, isCreator } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inspectSessionId, setInspectSessionId] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !isCreator) {
      navigate('/');
      return;
    }
    apiRequest('/sessions/mine/')
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setSessions(data.results || data);
        }
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated, isCreator, navigate]);

  const stats = useMemo(() => {
    const now = new Date();
    const upcoming = sessions.filter(s => new Date(s.start_time) > now).length;
    const totalBookings = sessions.reduce((sum, s) => sum + (s.booked_count || 0), 0);
    return {
      total: sessions.length,
      upcoming,
      totalBookings,
    };
  }, [sessions]);

  const handleDelete = async (sessionId) => {
    setDeleting(true);
    const res = await apiRequest(`/sessions/${sessionId}/delete/`, { method: 'DELETE' });
    if (res.ok) {
      setSessions(sessions.filter(s => s.id !== sessionId));
    }
    setDeleteConfirm(null);
    setDeleting(false);
  };

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  if (loading) {
    return (
      <div className="container">
        <h1>Creator Dashboard</h1>
        <p className="text-muted mb-3">Manage your sessions and monitor booking reliability.</p>
        <div className="stats-row">
          {[1, 2, 3].map(i => <div key={i} className="skeleton" style={{ height: 72 }} />)}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {[1, 2].map(i => <div key={i} className="skeleton" style={{ height: 64 }} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="container slide-up">
      <div className="dashboard-header">
        <div>
          <h1>Creator Dashboard</h1>
          <p className="dashboard-subtitle">Manage your sessions and monitor booking reliability.</p>
        </div>
        <Link to="/sessions/create" className="btn btn-primary">
          + New Session
        </Link>
      </div>

      {/* Real statistics from backend data */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Total Sessions</div>
          <div className="stat-value">{stats.total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Upcoming</div>
          <div className="stat-value">{stats.upcoming}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Bookings</div>
          <div className="stat-value">{stats.totalBookings}</div>
        </div>
      </div>

      {/* Session list */}
      {sessions.length === 0 ? (
        <div className="empty-state">
          <p>You haven't created any sessions yet.</p>
          <Link to="/sessions/create" className="btn btn-primary">
            Create Your First Session
          </Link>
        </div>
      ) : (
        <div className="session-list">
          {sessions.map((session) => (
            <div key={session.id} className="session-card-row">
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3>{session.title}</h3>
                <div className="session-meta" style={{ marginTop: '0.375rem' }}>
                  <span className="meta-item">
                    {formatDate(session.start_time)}
                  </span>
                  <span className="meta-item">
                    {session.booked_count}/{session.capacity} booked
                  </span>
                  {session.has_started ? (
                    <span className="badge badge-started">Started</span>
                  ) : session.remaining_seats === 0 ? (
                    <span className="badge badge-full">Full</span>
                  ) : (
                    <span className="badge badge-available">{session.remaining_seats} open</span>
                  )}
                </div>
              </div>
              <div className="session-card-actions">
                <button
                  onClick={() => setInspectSessionId(session.id)}
                  className="btn btn-ghost btn-sm"
                  title="Inspect booking integrity"
                >
                  🔍 Inspect
                </button>
                <Link to={`/sessions/${session.id}/edit`} className="btn btn-secondary btn-sm">
                  Edit
                </Link>
                <button
                  onClick={() => setDeleteConfirm(session)}
                  className="btn btn-danger btn-sm"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Integrity Console */}
      {inspectSessionId && (
        <BookingIntegrityConsole
          sessionId={inspectSessionId}
          onClose={() => setInspectSessionId(null)}
        />
      )}

      {/* Reliability Panel */}
      <div className="reliability-panel">
        <h2>Booking Reliability</h2>
        <div className="reliability-grid">
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Capacity protection
          </div>
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Duplicate prevention
          </div>
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Start-time enforcement
          </div>
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Concurrency locking (SELECT FOR UPDATE)
          </div>
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Idempotency key support
          </div>
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Database unique constraint
          </div>
          <div className="reliability-item">
            <span className="reliability-check">✓</span>
            Booking event audit trail
          </div>
        </div>
        <p className="text-xs mt-3" style={{ color: 'var(--text-tertiary)' }}>
          Protection status reflects implemented backend safeguards verified via
          automated concurrency tests (<code style={{ background: 'var(--bg-hover)', padding: '1px 4px', borderRadius: 3 }}>scripts/concurrency_test.py</code>).
        </p>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => !deleting && setDeleteConfirm(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Delete Session</h3>
            <p>
              Are you sure you want to delete "{deleteConfirm.title}"?
              This cannot be undone.
            </p>
            <div className="modal-actions">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="btn btn-secondary"
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm.id)}
                className="btn btn-danger"
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
