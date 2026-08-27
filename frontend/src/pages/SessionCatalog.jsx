import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function SessionCatalog() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/sessions/')
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load sessions');
        const data = await res.json();
        setSessions(data.results || data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-center"><div className="spinner" /></div>;
  if (error) return <div className="page-center"><div className="alert alert-error">{error}</div></div>;

  return (
    <div className="container">
      <h1>Session Catalog</h1>
      {sessions.length === 0 ? (
        <div className="empty-state">
          <p>No sessions available yet.</p>
        </div>
      ) : (
        <div className="session-grid">
          {sessions.map((session) => (
            <Link to={`/sessions/${session.id}`} key={session.id} className="session-card">
              <h3>{session.title}</h3>
              <p className="text-muted">by {session.creator_name}</p>
              <div className="session-meta">
                <span className="meta-item">
                  📅 {new Date(session.start_time).toLocaleDateString()}
                </span>
                <span className="meta-item">
                  🕐 {new Date(session.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <div className="session-availability">
                {session.has_started ? (
                  <span className="badge badge-muted">Started</span>
                ) : session.remaining_seats === 0 ? (
                  <span className="badge badge-full">Full</span>
                ) : (
                  <span className="badge badge-available">
                    {session.remaining_seats}/{session.capacity} seats
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
