"""
Pytest configuration and shared fixtures.
"""
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Set test environment variables before importing app
os.environ['ENVIRONMENT'] = 'test'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key-min-32-characters-long'
os.environ['OPENAI_API_KEY'] = 'sk-test-dummy-key'
os.environ['ENABLE_REDIS'] = 'false'
os.environ['DATABASE_NAME'] = 'panscience_test'


# Mock database and services before app import
@pytest.fixture(scope="session", autouse=True)
def setup_mocks():
    """Setup all necessary mocks before app initialization."""
    with patch('motor.motor_asyncio.AsyncIOMotorClient'), \
         patch('app.core.database.db_manager.connect', new_callable=AsyncMock), \
         patch('app.core.database.db_manager.disconnect', new_callable=AsyncMock), \
         patch('app.services.vector_store.FAISSVectorStore.add_vectors', new_callable=AsyncMock), \
         patch('app.services.vector_store.FAISSVectorStore.search', new_callable=AsyncMock):
        yield


@pytest.fixture(scope="session")
def client():
    """Create test client."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Generate auth headers with valid token."""
    from app.core.auth import create_access_token
    token = create_access_token({"sub": "test@example.com", "user_id": "test_user_123"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_database():
    """Mock database operations."""
    with patch('app.core.database.db_manager.get_database') as mock_db:
        mock_collection = MagicMock()
        mock_collection.find.return_value.to_list = AsyncMock(return_value=[])
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="test_id"))
        mock_collection.update_one = AsyncMock()
        mock_collection.delete_one = AsyncMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        
        mock_db.return_value.__getitem__ = lambda self, key: mock_collection
        yield mock_db


@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls."""
    with patch('openai.embeddings.create') as mock_embed:
        mock_embed.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )
        yield mock_embed


@pytest.fixture
def mock_vector_store():
    """Mock vector store operations."""
    with patch('app.services.vector_store.FAISSVectorStore') as mock_vs:
        mock_instance = MagicMock()
        mock_instance.add_vectors = AsyncMock()
        mock_instance.search = AsyncMock(return_value=[
            ({"chunk_id": "test_chunk", "text": "test content"}, 0.9)
        ])
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
