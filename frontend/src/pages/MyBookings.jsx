import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../api';

export default function MyBookings() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [activeBookings, setActiveBookings] = useState([]);
  const [pastBookings, setPastBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('active');

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    Promise.all([
      apiRequest('/bookings/mine/?status=active').then(r => r.json()),
      apiRequest('/bookings/mine/?status=past').then(r => r.json()),
    ])
      .then(([active, past]) => {
        setActiveBookings(active);
        setPastBookings(past);
      })
      .catch((err) => setError(err.message || 'Failed to load bookings'))
      .finally(() => setLoading(false));
  }, [isAuthenticated, navigate]);

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatTime = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div className="container">
        <h1>My Bookings</h1>
        <p className="text-muted mb-3">Manage your upcoming and previous sessions.</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton" style={{ height: 80 }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-center">
        <div className="alert alert-error">{error}</div>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }

  const bookings = tab === 'active' ? activeBookings : pastBookings;

  return (
    <div className="container slide-up">
      <h1>My Bookings</h1>
      <p className="text-muted mb-3">Manage your upcoming and previous sessions.</p>

      <div className="tab-bar">
        <button
          className={`tab ${tab === 'active' ? 'tab-active' : ''}`}
          onClick={() => setTab('active')}
        >
          Upcoming ({activeBookings.length})
        </button>
        <button
          className={`tab ${tab === 'past' ? 'tab-active' : ''}`}
          onClick={() => setTab('past')}
        >
          Past ({pastBookings.length})
        </button>
      </div>

      {bookings.length === 0 ? (
        <div className="empty-state">
          <p>
            {tab === 'active'
              ? "You don't have any upcoming bookings."
              : 'No past bookings to show.'}
          </p>
          {tab === 'active' && (
            <button onClick={() => navigate('/')} className="btn btn-primary">
              Browse Sessions
            </button>
          )}
        </div>
      ) : (
        <div className="booking-list">
          {bookings.map((booking) => (
            <Link
              key={booking.id}
              to={`/sessions/${booking.session}`}
              className="booking-card"
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <h3>{booking.session_title}</h3>
              <div className="session-meta" style={{ marginTop: '0.375rem' }}>
                <span className="meta-item">
                  <svg className="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="7" r="4" />
                    <path d="M5.5 21a6.5 6.5 0 0113 0" />
                  </svg>
                  {booking.creator_name}
                </span>
                <span className="meta-item">
                  <svg className="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="4" width="18" height="18" rx="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  {formatDate(booking.session_start_time)}
                </span>
                <span className="meta-item">
                  <svg className="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  {formatTime(booking.session_start_time)}
                </span>
                <span className={`badge ${booking.status === 'CONFIRMED' ? 'badge-available' : 'badge-muted'}`}>
                  {booking.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
