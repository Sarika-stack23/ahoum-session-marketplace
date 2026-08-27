import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function Navbar() {
  const { user, isAuthenticated, isCreator, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          Sessions Marketplace
        </Link>

        <div className="navbar-links">
          <Link to="/" className="nav-link">Browse</Link>

          {isAuthenticated ? (
            <>
              <Link to="/bookings" className="nav-link">My Bookings</Link>
              {isCreator && (
                <Link to="/dashboard" className="nav-link">Dashboard</Link>
              )}
              <Link to="/profile" className="nav-link">Profile</Link>
              <span className="nav-role">{user.role}</span>
              <button onClick={handleLogout} className="btn btn-secondary btn-sm">
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary btn-sm">
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
