import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest, parseError } from '../api';

export default function CreateSession() {
  const { isAuthenticated, isCreator } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: '',
    description: '',
    start_time: '',
    capacity: 1,
  });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isAuthenticated || !isCreator) {
    navigate('/');
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);

    try {
      const response = await apiRequest('/sessions/create/', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          start_time: new Date(form.start_time).toISOString(),
        }),
      });

      if (response.ok) {
        navigate('/dashboard');
      } else {
        const err = await parseError(response);
        setError(err.message);
      }
    } catch {
      setError('Could not connect to the server.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container slide-up">
      <h1>Create Session</h1>
      <p className="text-muted mb-3">Set up a new session for your audience.</p>

      <form onSubmit={handleSubmit} className="form">
        {error && <div className="alert alert-error">{error}</div>}

        <div className="form-group">
          <label htmlFor="title">Title</label>
          <input
            id="title"
            type="text"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
            maxLength={200}
            placeholder="e.g. Advanced React Workshop"
          />
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={4}
            placeholder="What will attendees learn or experience?"
          />
        </div>

        <div className="form-group">
          <label htmlFor="start_time">Start Time</label>
          <input
            id="start_time"
            type="datetime-local"
            value={form.start_time}
            onChange={(e) => setForm({ ...form, start_time: e.target.value })}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="capacity">Capacity</label>
          <input
            id="capacity"
            type="number"
            min={1}
            value={form.capacity}
            onChange={(e) => setForm({ ...form, capacity: parseInt(e.target.value) || 1 })}
            required
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? (
              <>
                <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                Creating...
              </>
            ) : (
              'Create Session'
            )}
          </button>
          <button type="button" onClick={() => navigate('/dashboard')} className="btn btn-secondary">
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
