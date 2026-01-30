import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, FileText, Video, Music } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStream } from '../hooks/useChat';
import './ChatInterface.css';
import SourceCard from './SourceCard';
import MediaPlayer from './MediaPlayer';

const ChatInterface = ({ documents }) => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [sources, setSources] = useState([]);
  const [mediaPlayer, setMediaPlayer] = useState(null);
  
  const { isStreaming, streamedContent, error, startStream, reset } = useChatStream();
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamedContent]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isStreaming) return;

    const userMessage = {
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setSources([]);
    reset();

    try {
      // First get non-streaming response to get sources
      const { chat } = await import('../services/api');
      const response = await chat(
        userMessage.content,
        selectedDocs.length > 0 ? selectedDocs : null,
        messages
      );

      setSources(response.sources || []);

      // Then stream the answer
      await startStream(
        userMessage.content,
        selectedDocs.length > 0 ? selectedDocs : null,
        messages
      );

      // Add assistant message
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: streamedContent || response.answer,
          timestamp: new Date(),
          sources: response.sources,
        },
      ]);
    } catch (err) {
      console.error('Chat error:', err);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, an error occurred while processing your request.',
          timestamp: new Date(),
          isError: true,
        },
      ]);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const getFileIcon = (fileType) => {
    switch (fileType) {
      case 'pdf':
        return <FileText size={16} />;
      case 'video':
        return <Video size={16} />;
      case 'audio':
        return <Music size={16} />;
      default:
        return <FileText size={16} />;
    }
  };

  const handlePlayTimestamp = (documentId, documentName, timestamp) => {
    // Find the document to get the file URL
    const doc = documents.find(d => d.id === documentId);
    if (doc && (doc.file_type === 'video' || doc.file_type === 'audio')) {
      // Get JWT token from localStorage
      const token = localStorage.getItem('token');
      // Use the media streaming endpoint with token as query parameter
      const mediaUrl = `http://localhost:8000/api/v1/media/${doc.file_path}${token ? `?token=${token}` : ''}`;
      setMediaPlayer({
        mediaUrl,
        fileName: documentName,
        startTime: timestamp
      });
    }
  };

  const handleCloseMediaPlayer = () => {
    setMediaPlayer(null);
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>AI Assistant</h2>
        <p>Ask questions about your uploaded documents</p>
      </div>

      {documents.length > 0 && (
        <div className="document-filter">
          <label>Filter by documents (optional):</label>
          <div className="document-chips">
            {documents.map((doc) => (
              <button
                key={doc.id}
                className={`chip ${selectedDocs.includes(doc.id) ? 'selected' : ''}`}
                onClick={() => {
                  setSelectedDocs((prev) =>
                    prev.includes(doc.id)
                      ? prev.filter((id) => id !== doc.id)
                      : [...prev, doc.id]
                  );
                }}
              >
                {getFileIcon(doc.file_type)}
                <span>{doc.file_name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h3>👋 Welcome to PanScience Q&A!</h3>
            <p>Upload documents and ask questions about their content.</p>
            <div className="example-questions">
              <p>Try asking:</p>
              <ul>
                <li>"What is the main topic of this document?"</li>
                <li>"Summarize the key points"</li>
                <li>"What was discussed at timestamp 2:30?"</li>
              </ul>
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={`message ${message.role} ${message.isError ? 'error' : ''}`}
          >
            <div className="message-avatar">
              {message.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className="message-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {message.sources && message.sources.length > 0 && (
                <div className="sources">
                  <h4>Sources:</h4>
                  <div className="sources-grid">
                    {message.sources.map((source, idx) => (
                      <SourceCard 
                        key={idx} 
                        source={source}
                        onPlayTimestamp={handlePlayTimestamp}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isStreaming && (
          <div className="message assistant streaming">
            <div className="message-avatar">🤖</div>
            <div className="message-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {streamedContent || '_Thinking..._'}
              </ReactMarkdown>
              {sources.length > 0 && (
                <div className="sources">
                  <h4>Sources:</h4>
                  <div className="sources-grid">
                    {sources.map((source, idx) => (
                      <SourceCard 
                        key={idx} 
                        source={source}
                        onPlayTimestamp={handlePlayTimestamp}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="message assistant error">
            <div className="message-avatar">⚠️</div>
            <div className="message-content">Error: {error}</div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-container">
        <textarea
          ref={inputRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask a question about your documents..."
          rows={1}
          disabled={isStreaming}
        />
        <button
          onClick={handleSendMessage}
          disabled={!inputValue.trim() || isStreaming}
          className="send-button"
        >
          {isStreaming ? (
            <Loader2 className="spinner" size={20} />
          ) : (
            <Send size={20} />
          )}
        </button>
      </div>

      {mediaPlayer && (
        <MediaPlayer
          mediaUrl={mediaPlayer.mediaUrl}
          fileName={mediaPlayer.fileName}
          startTime={mediaPlayer.startTime}
          onClose={handleCloseMediaPlayer}
        />
      )}
    </div>
  );
};

export default ChatInterface;
