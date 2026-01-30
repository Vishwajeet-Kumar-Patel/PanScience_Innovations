import React, { useState, useEffect } from 'react';
import { FileText, MessageSquare, BarChart3, LogIn, UserPlus, LogOut, User } from 'lucide-react';
import ChatInterface from './components/ChatInterface';
import FileUploader from './components/FileUploader';
import DocumentList from './components/DocumentList';
import LoginForm from './components/LoginForm';
import RegisterForm from './components/RegisterForm';
import { listDocuments, getCurrentUser } from './services/api';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [documents, setDocuments] = useState([]);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showLoginForm, setShowLoginForm] = useState(false);
  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    checkAuthentication();
    fetchDocuments();

    // Listen for auth-required events (from 401 responses)
    const handleAuthRequired = () => {
      setCurrentUser(null);
      setShowLoginForm(true);
    };
    window.addEventListener('auth-required', handleAuthRequired);
    return () => window.removeEventListener('auth-required', handleAuthRequired);
  }, []);

  const checkAuthentication = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const user = await getCurrentUser();
        setCurrentUser(user);
      } catch (error) {
        console.error('Auth check failed:', error);
        localStorage.removeItem('token');
      }
    }
    setAuthChecked(true);
  };

  const fetchDocuments = async () => {
    try {
      const docs = await listDocuments(0, 100);
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }
  };

  const handleUploadSuccess = () => {
    setRefreshTrigger(prev => prev + 1);
    fetchDocuments();
  };

  const handleDocumentRefresh = () => {
    fetchDocuments();
  };

  const handleLoginSuccess = async () => {
    await checkAuthentication();
    setShowLoginForm(false);
  };

  const handleRegisterSuccess = async () => {
    await checkAuthentication();
    setShowRegisterForm(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setCurrentUser(null);
  };

  const switchToRegister = () => {
    setShowLoginForm(false);
    setShowRegisterForm(true);
  };

  const switchToLogin = () => {
    setShowRegisterForm(false);
    setShowLoginForm(true);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="logo">
            <BarChart3 size={32} />
            <h1>PanScience Q&A</h1>
          </div>
          <p className="tagline">AI-Powered Document & Multimedia Assistant</p>
        </div>
        <div className="auth-section">
          {currentUser ? (
            <div className="user-info">
              <span className="user-name">
                <User size={18} />
                {currentUser.full_name || currentUser.email}
              </span>
              <button className="auth-button logout" onClick={handleLogout}>
                <LogOut size={18} />
                Logout
              </button>
            </div>
          ) : (
            <div className="auth-buttons">
              <button className="auth-button" onClick={() => setShowLoginForm(true)}>
                <LogIn size={18} />
                Login
              </button>
              <button className="auth-button primary" onClick={() => setShowRegisterForm(true)}>
                <UserPlus size={18} />
                Register
              </button>
            </div>
          )}
        </div>
      </header>

      <nav className="app-nav">
        <button
          className={`nav-button ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <MessageSquare size={20} />
          <span>Chat</span>
        </button>
        <button
          className={`nav-button ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          <FileText size={20} />
          <span>Documents</span>
        </button>
        <button
          className={`nav-button ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          <FileText size={20} />
          <span>Upload</span>
        </button>
      </nav>

      <main className="app-main">
        {activeTab === 'chat' && (
          <div className="tab-content">
            {documents.filter(d => d.status === 'completed').length === 0 ? (
              <div className="placeholder">
                <FileText size={64} />
                <h2>No documents available</h2>
                <p>Upload and process documents before starting a conversation</p>
                <button
                  className="primary-button"
                  onClick={() => setActiveTab('upload')}
                >
                  Upload Documents
                </button>
              </div>
            ) : (
              <ChatInterface documents={documents.filter(d => d.status === 'completed')} />
            )}
          </div>
        )}

        {activeTab === 'documents' && (
          <div className="tab-content">
            <DocumentList
              onRefresh={handleDocumentRefresh}
              refreshTrigger={refreshTrigger}
            />
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="tab-content upload-tab">
            <div className="upload-container">
              <h2>Upload Documents</h2>
              <p className="upload-description">
                Upload PDFs, audio, or video files to ask questions about their content
              </p>
              <FileUploader onUploadSuccess={handleUploadSuccess} />
            </div>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>
          &copy; 2026 PanScience Q&A • Built with FastAPI, React & Free AI Services
        </p>
      </footer>

      {/* Authentication Modals */}
      {showLoginForm && (
        <LoginForm
          onClose={() => setShowLoginForm(false)}
          onSwitchToRegister={switchToRegister}
          onLoginSuccess={handleLoginSuccess}
        />
      )}
      {showRegisterForm && (
        <RegisterForm
          onClose={() => setShowRegisterForm(false)}
          onSwitchToLogin={switchToLogin}
          onRegisterSuccess={handleRegisterSuccess}
        />
      )}
    </div>
  );
}

export default App;
