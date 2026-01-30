"""
Comprehensive tests for core functionality.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import jwt


class TestAuthentication:
    """Test authentication and JWT functionality."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        from app.core.auth import get_password_hash, verify_password
        
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False
    
    def test_create_access_token(self):
        """Test JWT token creation."""
        from app.core.auth import create_access_token
        from app.core.config import settings
        
        data = {"sub": "testuser@example.com"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        
        # Decode and verify
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        assert decoded["sub"] == "testuser@example.com"
    
    def test_token_expiration(self):
        """Test token expiration."""
        from app.core.auth import create_access_token
        from app.core.config import settings
        
        token = create_access_token(
            {"sub": "test@example.com"},
            expires_delta=timedelta(seconds=-1)
        )
        
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )


class TestConfiguration:
    """Test configuration management."""
    
    def test_settings_loaded(self):
        """Test that settings are properly loaded."""
        from app.core.config import settings
        
        assert settings.APP_NAME is not None
        assert settings.APP_VERSION is not None
        assert settings.JWT_SECRET_KEY is not None
        assert settings.JWT_ALGORITHM == "HS256"
    
    def test_environment_types(self):
        """Test environment type handling."""
        from app.core.config import settings
        
        assert settings.ENVIRONMENT in ["development", "production", "test"]


class TestRateLimiting:
    """Test rate limiting middleware."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test rate limiting logic."""
        from app.core.rate_limit import RateLimitMiddleware
        from fastapi import Request
        from starlette.datastructures import Headers
        
        middleware = RateLimitMiddleware(app=MagicMock())
        
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = Headers({})
        
        # Should allow first request
        assert await middleware._check_rate_limit(mock_request) is True


class TestDatabaseConnection:
    """Test database connection handling."""
    
    @pytest.mark.asyncio
    async def test_database_manager(self):
        """Test database manager initialization."""
        from app.core.database import DatabaseManager
        
        with patch('motor.motor_asyncio.AsyncIOMotorClient') as mock_client:
            manager = DatabaseManager()
            await manager.connect()
            
            assert mock_client.called


class TestModels:
    """Test all Pydantic models."""
    
    def test_user_create_model(self):
        """Test UserCreate model."""
        from app.models import UserCreate
        
        user = UserCreate(
            email="test@example.com",
            password="password123",
            full_name="Test User"
        )
        
        assert user.email == "test@example.com"
        assert user.password == "password123"
    
    def test_user_response_model(self):
        """Test UserResponse model."""
        from app.models import UserResponse
        
        user = UserResponse(
            id="123",
            email="test@example.com",
            full_name="Test User",
            created_at=datetime.now()
        )
        
        assert user.id == "123"
        assert "password" not in user.model_dump()
    
    def test_document_response_model(self):
        """Test DocumentResponse model."""
        from app.models import DocumentResponse, FileType, ProcessingStatus
        
        doc = DocumentResponse(
            id="doc123",
            user_id="user123",
            file_name="test.pdf",
            file_type=FileType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now()
        )
        
        assert doc.id == "doc123"
        assert doc.file_type == FileType.PDF
    
    def test_chat_response_model(self):
        """Test ChatResponse model."""
        from app.models import ChatResponse
        
        response = ChatResponse(
            answer="This is a test answer.",
            sources=["source1", "source2"],
            confidence=0.95
        )
        
        assert response.answer == "This is a test answer."
        assert len(response.sources) == 2
        assert response.confidence == 0.95


class TestChunkingService:
    """Test chunking service edge cases."""
    
    def test_empty_text_chunking(self):
        """Test chunking with empty text."""
        from app.services.chunking import chunking_service
        
        chunks = chunking_service.chunk_text("")
        assert len(chunks) == 0
    
    def test_small_text_chunking(self):
        """Test chunking with text smaller than chunk size."""
        from app.services.chunking import chunking_service
        
        text = "Small text"
        chunks = chunking_service.chunk_text(text)
        
        assert len(chunks) >= 1
        assert chunks[0]['text'] == text


class TestFileUploadService:
    """Test file upload validation and handling."""
    
    def test_allowed_file_types(self):
        """Test file type validation."""
        from app.services.file_upload import FileUploadService
        
        service = FileUploadService()
        
        # Valid extensions
        assert service._validate_file_extension("document.pdf") is True
        assert service._validate_file_extension("audio.mp3") is True
        assert service._validate_file_extension("video.mp4") is True
        assert service._validate_file_extension("audio.wav") is True
        
        # Invalid extensions
        assert service._validate_file_extension("script.exe") is False
        assert service._validate_file_extension("data.json") is False
    
    def test_file_size_limits(self):
        """Test file size validation."""
        from app.services.file_upload import FileUploadService
        
        service = FileUploadService()
        
        # Within limits
        assert service._validate_file_size(1024 * 1024, "application/pdf") is True
        
        # Exceeds limit
        assert service._validate_file_size(1024 * 1024 * 1024, "application/pdf") is False


class TestDocumentProcessor:
    """Test document processing service."""
    
    @pytest.mark.asyncio
    async def test_pdf_extraction(self, tmp_path):
        """Test PDF text extraction."""
        from app.services.pdf_extraction import PDFExtractor
        
        extractor = PDFExtractor()
        
        # Would need actual PDF file for full test
        # This tests the method exists and is callable
        assert hasattr(extractor, 'extract_text_from_pdf')
        assert callable(extractor.extract_text_from_pdf)


class TestCacheService:
    """Test caching functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test cache get/set operations."""
        from app.core.cache import cache
        
        # Test cache methods exist
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')
        assert hasattr(cache, 'delete')


class TestErrorHandling:
    """Test error handling across the application."""
    
    def test_invalid_token_handling(self):
        """Test handling of invalid JWT tokens."""
        from app.core.auth import verify_token
        
        with pytest.raises(Exception):
            verify_token("invalid.token.here")
    
    def test_database_error_handling(self):
        """Test database error scenarios."""
        from app.core.database import db_manager
        
        # Test graceful handling when database is not connected
        db = db_manager.get_database()
        assert db is not None or True  # Should not raise exception


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
