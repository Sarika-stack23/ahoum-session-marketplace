import { Routes, Route } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Navbar from './components/Navbar';
import SessionCatalog from './pages/SessionCatalog';
import SessionDetail from './pages/SessionDetail';
import Login from './pages/Login';
import OAuthCallback from './pages/OAuthCallback';
import MyBookings from './pages/MyBookings';
import CreatorDashboard from './pages/CreatorDashboard';
import CreateSession from './pages/CreateSession';
import EditSession from './pages/EditSession';
import Profile from './pages/Profile';

export default function App() {
  const { loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <Navbar />
      <main className="main-content">
        <Routes>
          {/* Public */}
          <Route path="/" element={<SessionCatalog />} />
          <Route path="/sessions/:id" element={<SessionDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/auth/callback" element={<OAuthCallback />} />

          {/* Authenticated */}
          <Route path="/bookings" element={<MyBookings />} />
          <Route path="/profile" element={<Profile />} />

          {/* Creator */}
          <Route path="/dashboard" element={<CreatorDashboard />} />
          <Route path="/sessions/create" element={<CreateSession />} />
          <Route path="/sessions/:id/edit" element={<EditSession />} />
        </Routes>
      </main>
    </div>
  );
}
