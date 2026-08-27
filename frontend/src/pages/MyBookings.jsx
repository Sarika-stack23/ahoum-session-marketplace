import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest } from '../api';

export default function MyBookings() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [activeBookings, setActiveBookings] = useState([]);
  const [pastBookings, setPastBookings] = useState([]);
  const [loading, setLoading] = useState(true);
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
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [isAuthenticated, navigate]);

  if (loading) return <div className="page-center"><div className="spinner" /></div>;

  const bookings = tab === 'active' ? activeBookings : pastBookings;

  return (
    <div className="container">
      <h1>My Bookings</h1>

      <div className="tab-bar">
        <button
          className={`tab ${tab === 'active' ? 'tab-active' : ''}`}
          onClick={() => setTab('active')}
        >
          Active ({activeBookings.length})
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
          <p>No {tab} bookings.</p>
          {tab === 'active' && (
            <button onClick={() => navigate('/')} className="btn btn-primary">
              Browse Sessions
            </button>
          )}
        </div>
      ) : (
        <div className="booking-list">
          {bookings.map((booking) => (
            <div key={booking.id} className="booking-card">
              <h3>{booking.session_title}</h3>
              <p className="text-muted">by {booking.creator_name}</p>
              <div className="session-meta">
                <span className="meta-item">
                  📅 {new Date(booking.session_start_time).toLocaleDateString()}
                </span>
                <span className="meta-item">
                  🕐 {new Date(booking.session_start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className={`badge ${booking.status === 'CONFIRMED' ? 'badge-available' : 'badge-muted'}`}>
                  {booking.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
