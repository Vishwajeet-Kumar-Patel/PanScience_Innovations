import React from 'react';
import { FileText, Play } from 'lucide-react';
import { useTimestampFormatter } from '../hooks/useChat';
import './SourceCard.css';

const SourceCard = ({ source, onPlayTimestamp }) => {
  const { formatTimestamp } = useTimestampFormatter();

  const handlePlayTimestamp = (timestamp) => {
    if (onPlayTimestamp) {
      onPlayTimestamp(source.document_id, source.document_name, timestamp);
    }
  };

  return (
    <div className="source-card">
      <div className="source-header">
        <FileText size={16} />
        <span className="source-doc-name">{source.document_name}</span>
      </div>
      
      <div className="source-content">
        <p className="source-text">{source.chunk_text}</p>
      </div>

      <div className="source-footer">
        {source.page_number && (
          <span className="source-meta">Page {source.page_number}</span>
        )}
        
        {source.timestamps && source.timestamps.length > 0 && (
          <div className="timestamp-actions">
            {source.timestamps.slice(0, 2).map((ts, idx) => (
              <button
                key={idx}
                className="timestamp-button"
                onClick={() => handlePlayTimestamp(ts.start)}
                title={`Play from ${formatTimestamp(ts.start)}`}
              >
                <Play size={14} />
                <span>{formatTimestamp(ts.start)}</span>
              </button>
            ))}
          </div>
        )}
        
        <span className="source-score">
          {(source.relevance_score * 100).toFixed(0)}% match
        </span>
      </div>
    </div>
  );
};

export default SourceCard;
