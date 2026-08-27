import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiRequest, parseError } from '../api';

export default function EditSession() {
  const { id } = useParams();
  const { isAuthenticated, isCreator } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !isCreator) {
      navigate('/');
      return;
    }
    fetch(`/api/sessions/${id}/`)
      .then(async (res) => {
        if (!res.ok) throw new Error('Session not found');
        const data = await res.json();
        setForm({
          title: data.title,
          description: data.description || '',
          start_time: data.start_time.slice(0, 16),
          capacity: data.capacity,
        });
      })
      .catch(() => navigate('/dashboard'));
  }, [id, isAuthenticated, isCreator, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await apiRequest(`/sessions/${id}/update/`, {
        method: 'PATCH',
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

  if (!form) return <div className="page-center"><div className="spinner" /></div>;

  return (
    <div className="container">
      <h1>Edit Session</h1>
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
          />
        </div>

        <div className="form-group">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={4}
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
            {submitting ? 'Saving...' : 'Save Changes'}
          </button>
          <button type="button" onClick={() => navigate('/dashboard')} className="btn btn-secondary">
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
