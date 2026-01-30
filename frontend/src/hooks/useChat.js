import { useState, useCallback } from 'react';
import { chatStream } from '../services/api';

/**
 * Custom hook for streaming chat responses
 */
export const useChatStream = () => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedContent, setStreamedContent] = useState('');
  const [error, setError] = useState(null);

  const startStream = useCallback(async (question, documentIds, conversationHistory) => {
    setIsStreaming(true);
    setStreamedContent('');
    setError(null);

    try {
      await chatStream(
        question,
        documentIds,
        conversationHistory,
        (chunk) => {
          setStreamedContent((prev) => prev + chunk);
        }
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsStreaming(false);
    }
  }, []);

  const reset = useCallback(() => {
    setStreamedContent('');
    setError(null);
  }, []);

  return {
    isStreaming,
    streamedContent,
    error,
    startStream,
    reset,
  };
};

/**
 * Hook for managing document uploads
 */
export const useFileUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const upload = useCallback(async (file, uploadFn) => {
    setUploading(true);
    setProgress(0);
    setError(null);

    try {
      const result = await uploadFn(file, (percent) => {
        setProgress(percent);
      });
      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }, []);

  return {
    uploading,
    progress,
    error,
    upload,
  };
};

/**
 * Hook for formatting timestamps
 */
export const useTimestampFormatter = () => {
  const formatTimestamp = useCallback((seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes
        .toString()
        .padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
      return `${minutes.toString().padStart(2, '0')}:${secs
        .toString()
        .padStart(2, '0')}`;
    }
  }, []);

  return { formatTimestamp };
};
