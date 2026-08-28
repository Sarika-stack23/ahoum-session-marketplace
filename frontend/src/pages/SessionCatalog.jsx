import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';

export default function SessionCatalog() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');

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

  const getStatus = (session) => {
    if (session.has_started) return 'started';
    if (session.remaining_seats === 0) return 'full';
    if (session.remaining_seats <= Math.ceil(session.capacity * 0.2)) return 'almost-full';
    return 'available';
  };

  const filtered = useMemo(() => {
    return sessions.filter((s) => {
      const q = search.toLowerCase();
      const matchSearch = !q ||
        s.title.toLowerCase().includes(q) ||
        (s.creator_name || '').toLowerCase().includes(q);

      const status = getStatus(s);
      const matchFilter =
        filter === 'all' ||
        (filter === 'available' && (status === 'available' || status === 'almost-full')) ||
        (filter === 'almost-full' && status === 'almost-full') ||
        (filter === 'full' && status === 'full') ||
        (filter === 'started' && status === 'started');

      return matchSearch && matchFilter;
    });
  }, [sessions, search, filter]);

  const getCapacityLevel = (session) => {
    const ratio = (session.capacity - session.remaining_seats) / session.capacity;
    if (ratio >= 1) return 'full';
    if (ratio >= 0.8) return 'high';
    if (ratio >= 0.5) return 'medium';
    return 'low';
  };

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
        <div className="hero">
          <h1>Find your next session</h1>
          <p>Discover live sessions and reserve your seat before they're full.</p>
        </div>
        <div className="session-grid">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton skeleton-card" />
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

  return (
    <div className="container slide-up">
      <div className="hero">
        <h1>Find your next session</h1>
        <p>Discover live sessions and reserve your seat before they're full.</p>
      </div>

      <div className="toolbar">
        <div className="search-wrapper">
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            className="search-input"
            placeholder="Search sessions or creators..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-group">
          {['all', 'available', 'almost-full', 'full', 'started'].map((f) => (
            <button
              key={f}
              className={`filter-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? 'All' : f === 'almost-full' ? 'Almost Full' : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="result-count">
        {filtered.length} {filtered.length === 1 ? 'session' : 'sessions'} found
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <p>No sessions match your criteria.</p>
          {(search || filter !== 'all') && (
            <button className="btn btn-secondary" onClick={() => { setSearch(''); setFilter('all'); }}>
              Clear Filters
            </button>
          )}
        </div>
      ) : (
        <div className="session-grid">
          {filtered.map((session) => {
            const status = getStatus(session);
            const capLevel = getCapacityLevel(session);
            const fillPct = Math.round(((session.capacity - session.remaining_seats) / session.capacity) * 100);

            return (
              <Link to={`/sessions/${session.id}`} key={session.id} className="session-card">
                <div className="session-card-title">{session.title}</div>
                <div className="session-card-creator">by {session.creator_name}</div>

                <div className="session-card-meta">
                  <span className="meta-item">
                    <svg className="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="4" width="18" height="18" rx="2" />
                      <line x1="16" y1="2" x2="16" y2="6" />
                      <line x1="8" y1="2" x2="8" y2="6" />
                      <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                    {formatDate(session.start_time)}
                  </span>
                  <span className="meta-item">
                    <svg className="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    {formatTime(session.start_time)}
                  </span>
                </div>

                <div className="session-card-footer">
                  <div>
                    <div className="capacity-bar">
                      <div
                        className={`capacity-fill ${capLevel}`}
                        style={{ width: `${fillPct}%` }}
                      />
                    </div>
                    <span className="capacity-text">
                      {session.remaining_seats}/{session.capacity} seats
                    </span>
                  </div>
                  <span className={`badge badge-${status}`}>
                    {status === 'available' && 'Available'}
                    {status === 'almost-full' && 'Almost Full'}
                    {status === 'full' && 'Full'}
                    {status === 'started' && 'Started'}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
