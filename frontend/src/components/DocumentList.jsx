import React, { useState, useEffect } from 'react';
import { FileText, Video, Music, Trash2, RefreshCw, Clock, CheckCircle, AlertCircle } from 'lucide-react';
import { listDocuments, deleteDocument, getStats } from '../services/api';
import './DocumentList.css';

const DocumentList = ({ onRefresh, refreshTrigger }) => {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);

  useEffect(() => {
    fetchDocuments();
    fetchStats();
  }, [refreshTrigger]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const docs = await listDocuments(0, 50);
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const handleDelete = async (documentId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      setDeleting(documentId);
      await deleteDocument(documentId);
      await fetchDocuments();
      await fetchStats();
      if (onRefresh) onRefresh();
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document');
    } finally {
      setDeleting(null);
    }
  };

  const getFileIcon = (fileType) => {
    switch (fileType) {
      case 'pdf':
        return <FileText size={20} />;
      case 'video':
        return <Video size={20} />;
      case 'audio':
        return <Music size={20} />;
      default:
        return <FileText size={20} />;
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="status-icon completed" />;
      case 'processing':
        return <RefreshCw size={16} className="status-icon processing spin" />;
      case 'failed':
        return <AlertCircle size={16} className="status-icon failed" />;
      default:
        return <Clock size={16} className="status-icon pending" />;
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="document-list">
      <div className="list-header">
        <h2>Your Documents</h2>
        <button className="refresh-button" onClick={fetchDocuments} disabled={loading}>
          <RefreshCw size={18} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_documents}</div>
            <div className="stat-label">Total Documents</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.status_counts?.completed || 0}</div>
            <div className="stat-label">Processed</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.status_counts?.processing || 0}</div>
            <div className="stat-label">Processing</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_chunks}</div>
            <div className="stat-label">Total Chunks</div>
          </div>
        </div>
      )}

      {loading && documents.length === 0 ? (
        <div className="loading-state">
          <RefreshCw size={48} className="spin" />
          <p>Loading documents...</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="empty-state">
          <FileText size={48} />
          <h3>No documents yet</h3>
          <p>Upload your first document to get started</p>
        </div>
      ) : (
        <div className="documents-grid">
          {documents.map((doc) => (
            <div key={doc.id} className="document-card">
              <div className="card-header">
                <div className="file-icon-large">
                  {getFileIcon(doc.file_type)}
                </div>
                <div className="status-badge">
                  {getStatusIcon(doc.status)}
                  <span>{doc.status}</span>
                </div>
              </div>

              <div className="card-body">
                <h3 className="doc-title" title={doc.file_name}>
                  {doc.file_name}
                </h3>
                
                <div className="doc-metadata">
                  <div className="meta-item">
                    <span className="meta-label">Size:</span>
                    <span className="meta-value">{formatFileSize(doc.file_size)}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Chunks:</span>
                    <span className="meta-value">{doc.chunk_count}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Uploaded:</span>
                    <span className="meta-value">{formatDate(doc.created_at)}</span>
                  </div>
                </div>
              </div>

              <div className="card-footer">
                <button
                  className="delete-button"
                  onClick={() => handleDelete(doc.id)}
                  disabled={deleting === doc.id}
                >
                  <Trash2 size={16} />
                  {deleting === doc.id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DocumentList;
