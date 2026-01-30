"""
Tests for API endpoints.
Run with: pytest -v
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test health and root endpoints."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app_name" in data
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestUploadEndpoints:
    """Test file upload endpoints."""
    
    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self):
        """Test uploading invalid file type."""
        # Create a fake text file
        files = {"file": ("test.txt", b"test content", "text/plain")}
        response = client.post("/api/v1/upload/", files=files)
        
        # Should fail validation
        assert response.status_code in [400, 413, 422]
    
    @pytest.mark.asyncio
    async def test_upload_no_file(self):
        """Test upload without file."""
        response = client.post("/api/v1/upload/")
        assert response.status_code == 422  # Validation error


class TestDocumentEndpoints:
    """Test document management endpoints."""
    
    def test_list_documents(self):
        """Test listing documents."""
        response = client.get("/api/v1/documents/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_nonexistent_document(self):
        """Test getting non-existent document."""
        response = client.get("/api/v1/documents/nonexistent_id")
        assert response.status_code == 404
    
    def test_get_stats(self):
        """Test getting statistics."""
        response = client.get("/api/v1/documents/stats/overview")
        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "status_counts" in data


class TestChatEndpoints:
    """Test chat endpoints."""
    
    def test_chat_without_documents(self):
        """Test chat when no documents exist."""
        response = client.post(
            "/api/v1/chat/",
            json={"question": "What is this about?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
    
    def test_chat_invalid_request(self):
        """Test chat with invalid request."""
        response = client.post(
            "/api/v1/chat/",
            json={"question": ""}  # Empty question
        )
        assert response.status_code == 422  # Validation error
    
    def test_semantic_search(self):
        """Test semantic search endpoint."""
        response = client.post(
            "/api/v1/chat/search",
            json={"query": "test query", "top_k": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
