"""
Pytest configuration and shared fixtures.
"""
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Set test environment variables before importing app
os.environ['ENVIRONMENT'] = 'test'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key'
os.environ['OPENAI_API_KEY'] = 'sk-test-dummy-key'
os.environ['ENABLE_REDIS'] = 'false'


@pytest.fixture(scope="session", autouse=True)
def mock_database():
    """Mock database connections for all tests."""
    with patch('app.core.database.db_manager.connect', new_callable=AsyncMock), \
         patch('app.core.database.db_manager.disconnect', new_callable=AsyncMock), \
         patch('app.core.database.db_manager.get_database') as mock_db:
        
        # Mock database methods
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        yield mock_db_instance


@pytest.fixture(scope="session", autouse=True)
def mock_cache():
    """Mock Redis cache for all tests."""
    with patch('app.core.cache.cache.close', new_callable=AsyncMock):
        yield


@pytest.fixture(scope="function")
def mock_openai():
    """Mock OpenAI API calls."""
    with patch('app.services.free_embeddings.get_free_embedding') as mock_embed, \
         patch('app.services.free_llm.get_free_llm_response') as mock_llm:
        
        # Mock embedding response (1536 dimensions)
        mock_embed.return_value = [0.1] * 1536
        
        # Mock LLM response
        mock_llm.return_value = "This is a test response."
        
        yield {
            'embed': mock_embed,
            'llm': mock_llm
        }


@pytest.fixture(scope="function")
def mock_vector_store():
    """Mock vector store operations."""
    with patch('app.services.vector_store.VectorStore') as mock_vs:
        mock_instance = MagicMock()
        mock_instance.add_documents = AsyncMock()
        mock_instance.search = AsyncMock(return_value=[])
        mock_instance.delete_by_document_id = AsyncMock()
        mock_vs.return_value = mock_instance
        
        yield mock_instance


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing."""
    return {
        "filename": "test.pdf",
        "content_type": "application/pdf",
        "size": 1024
    }


@pytest.fixture
def sample_audio_file():
    """Create a sample audio file for testing."""
    return {
        "filename": "test.mp3",
        "content_type": "audio/mpeg",
        "size": 2048
    }


@pytest.fixture
def sample_video_file():
    """Create a sample video file for testing."""
    return {
        "filename": "test.mp4",
        "content_type": "video/mp4",
        "size": 4096
    }
