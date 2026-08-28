import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Profile() {
  const { user, isAuthenticated, updateProfile } = useAuth();
  const navigate = useNavigate();
  const [bio, setBio] = useState(user?.bio || '');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
    }
  }, [isAuthenticated, navigate]);

  if (!isAuthenticated) {
    return null;
  }


  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    const result = await updateProfile({ bio });
    if (result.success) {
      setMessage({ type: 'success', text: 'Profile saved successfully.' });
    } else {
      setMessage({ type: 'error', text: result.error?.message || 'Update failed.' });
    }
    setSaving(false);
  };

  return (
    <div className="container slide-up">
      <h1>Profile</h1>
      <p className="text-muted mb-3">Manage your account information.</p>

      <div className="card profile-card">
        <div className="profile-info">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" className="avatar" />
          ) : (
            <div className="avatar" style={{
              background: 'var(--accent-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
              fontWeight: 700,
              color: 'var(--accent)',
            }}>
              {(user.username || '?')[0].toUpperCase()}
            </div>
          )}
          <div>
            <div className="profile-name">{user.username}</div>
            <div className="profile-email">{user.email}</div>
            <span className="badge badge-accent" style={{ marginTop: '0.375rem' }}>{user.role}</span>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="bio">Bio</label>
          <textarea
            id="bio"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            rows={3}
            maxLength={500}
            placeholder="Tell others a little about yourself..."
          />
          <div className="text-xs text-tertiary mt-1" style={{ textAlign: 'right' }}>
            {bio.length}/500
          </div>
        </div>

        {message && (
          <div className={`alert alert-${message.type}`}>
            {message.text}
          </div>
        )}

        <button onClick={handleSave} className="btn btn-primary" disabled={saving}>
          {saving ? (
            <>
              <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              Saving...
            </>
          ) : (
            'Save Profile'
          )}
        </button>
      </div>
    </div>
  );
}
