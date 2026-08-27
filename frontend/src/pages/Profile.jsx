import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Profile() {
  const { user, isAuthenticated, updateProfile } = useAuth();
  const navigate = useNavigate();
  const [bio, setBio] = useState(user?.bio || '');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  if (!isAuthenticated) {
    navigate('/login');
    return null;
  }

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    const result = await updateProfile({ bio });
    if (result.success) {
      setMessage({ type: 'success', text: 'Profile updated.' });
    } else {
      setMessage({ type: 'error', text: result.error?.message || 'Update failed.' });
    }
    setSaving(false);
  };

  return (
    <div className="container">
      <h1>Profile</h1>
      <div className="card">
        <div className="profile-info">
          {user.avatar_url && (
            <img src={user.avatar_url} alt="Avatar" className="avatar" />
          )}
          <div>
            <h2>{user.username}</h2>
            <p className="text-muted">{user.email}</p>
            <span className="badge badge-available">{user.role}</span>
          </div>
        </div>

        <div className="form-group" style={{marginTop: '1.5rem'}}>
          <label htmlFor="bio">Bio</label>
          <textarea
            id="bio"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            rows={3}
            maxLength={500}
          />
        </div>

        {message && (
          <div className={`alert alert-${message.type}`}>{message.text}</div>
        )}

        <button onClick={handleSave} className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </div>
    </div>
  );
}
