import React, { useState } from 'react';
import { LogIn, X } from 'lucide-react';
import './AuthForms.css';

const LoginForm = ({ onClose, onSwitchToRegister, onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('token', data.access_token);
        onLoginSuccess?.(data);
        onClose();
      } else {
        // Handle FastAPI validation errors (422) and other errors
        if (Array.isArray(data.detail)) {
          // FastAPI validation error format
          const errorMessages = data.detail.map(err => err.msg).join(', ');
          setError(errorMessages);
        } else if (typeof data.detail === 'string') {
          setError(data.detail);
        } else {
          setError('Login failed');
        }
      }
    } catch (error) {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="auth-modal-header">
          <h2>
            <LogIn size={24} />
            Login to PanScience
          </h2>
          <button className="close-button" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          <button type="submit" className="submit-button" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>

          <div className="auth-switch">
            Don't have an account?{' '}
            <button
              type="button"
              className="switch-button"
              onClick={onSwitchToRegister}
            >
              Register here
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginForm;
