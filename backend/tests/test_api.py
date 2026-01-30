"""
Tests for API endpoints.
Run with: pytest -v
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestHealthEndpoints:
    """Test health and root endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app_name" in data
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestUploadEndpoints:
    """Test file upload endpoints."""
    
    def test_upload_invalid_file_type(self, client, auth_headers):
        """Test uploading invalid file type."""
        files = {"file": ("test.txt", b"test content", "text/plain")}
        response = client.post("/api/v1/upload/", files=files, headers=auth_headers)
        assert response.status_code in [400, 415, 422]
    
    def test_upload_no_file(self, client, auth_headers):
        """Test upload without file."""
        response = client.post("/api/v1/upload/", headers=auth_headers)
        assert response.status_code == 422


class TestDocumentEndpoints:
    """Test document management endpoints."""
    
    def test_list_documents(self, client, auth_headers, mock_database):
        """Test listing documents."""
        with patch('app.api.documents.get_current_user', return_value={"id": "test_user"}):
            response = client.get("/api/v1/documents/", headers=auth_headers)
            assert response.status_code == 200
            assert isinstance(response.json(), list)
    
    def test_get_nonexistent_document(self, client, auth_headers, mock_database):
        """Test getting non-existent document."""
        with patch('app.api.documents.get_current_user', return_value={"id": "test_user"}):
            response = client.get("/api/v1/documents/nonexistent_id", headers=auth_headers)
            assert response.status_code == 404
    
    def test_get_stats(self, client, auth_headers, mock_database):
        """Test getting statistics."""
        with patch('app.api.documents.get_current_user', return_value={"id": "test_user"}):
            response = client.get("/api/v1/documents/stats/overview", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert "total_documents" in data


class TestChatEndpoints:
    """Test chat endpoints."""
    
    def test_chat_without_documents(self, client, auth_headers, mock_database, mock_vector_store):
        """Test chat when no documents exist."""
        with patch('app.api.chat.get_current_user', return_value={"id": "test_user"}), \
             patch('app.services.rag_chat.RAGChatService.answer_question', 
                   new_callable=AsyncMock, 
                   return_value={"answer": "Test answer", "sources": []}):
            response = client.post(
                "/api/v1/chat/",
                json={"question": "What is this about?"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_chat_invalid_request(self, client, auth_headers):
        """Test chat with invalid request."""
        response = client.post(
            "/api/v1/chat/",
            json={"question": ""},
            headers=auth_headers
        )
        assert response.status_code == 422
    
    def test_semantic_search(self, client, auth_headers, mock_vector_store):
        """Test semantic search endpoint."""
        with patch('app.api.chat.get_current_user', return_value={"id": "test_user"}):
            response = client.post(
                "/api/v1/chat/search",
                json={"query": "test query", "top_k": 5},
                headers=auth_headers
            )
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
