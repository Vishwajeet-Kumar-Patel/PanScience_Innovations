/**
 * API service for communicating with the backend.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add authentication token to all requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle 401 unauthorized responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new CustomEvent('auth-required'));
    }
    return Promise.reject(error);
  }
);

// Upload services
export const uploadFile = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/upload/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        onProgress(percentCompleted);
      }
    },
  });

  return response.data;
};

export const uploadMultipleFiles = async (files, onProgress) => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await api.post('/upload/batch', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        onProgress(percentCompleted);
      }
    },
  });

  return response.data;
};

// Document services
export const listDocuments = async (skip = 0, limit = 20, statusFilter = null) => {
  const params = { skip, limit };
  if (statusFilter) {
    params.status_filter = statusFilter;
  }

  const response = await api.get('/documents/', { params });
  return response.data;
};

export const getDocument = async (documentId) => {
  const response = await api.get(`/documents/${documentId}`);
  return response.data;
};

export const deleteDocument = async (documentId) => {
  await api.delete(`/documents/${documentId}`);
};

export const summarizeDocument = async (documentId, maxLength = 500) => {
  const response = await api.post(`/documents/${documentId}/summarize`, {
    document_id: documentId,
    max_length: maxLength,
  });
  return response.data;
};

export const getStats = async () => {
  const response = await api.get('/documents/stats/overview');
  return response.data;
};

// Chat services
export const chat = async (question, documentIds = null, conversationHistory = []) => {
  const response = await api.post('/chat/', {
    question,
    document_ids: documentIds,
    conversation_history: conversationHistory,
    stream: false,
  });
  return response.data;
};

export const chatStream = async (question, documentIds = null, conversationHistory = [], onChunk) => {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
  };
  
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      question,
      document_ids: documentIds,
      conversation_history: conversationHistory,
      stream: true,
    }),
  });

  if (!response.ok) {
    throw new Error('Chat stream failed');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          if (data.content) {
            onChunk(data.content);
          } else if (data.done) {
            return;
          } else if (data.error) {
            throw new Error(data.error);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
};

export const semanticSearch = async (query, documentIds = null, topK = 5) => {
  const response = await api.post('/chat/search', {
    query,
    document_ids: documentIds,
    top_k: topK,
  });
  return response.data;
};

// Authentication services
export const loginUser = async (email, password) => {
  const response = await axios.post(`${API_BASE_URL}${API_PREFIX}/auth/login`, {
    email,
    password,
  });
  return response.data;
};

export const registerUser = async (email, fullName, password) => {
  const response = await axios.post(`${API_BASE_URL}${API_PREFIX}/auth/register`, {
    email,
    full_name: fullName,
    password,
  });
  return response.data;
};

export const getCurrentUser = async () => {
  const token = localStorage.getItem('token');
  if (!token) {
    throw new Error('No authentication token');
  }

  const response = await axios.get(`${API_BASE_URL}${API_PREFIX}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return response.data;
};

export default api;
