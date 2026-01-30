"""
Basic tests for document processing services.
Run with: pytest -v
"""
import pytest
from pathlib import Path
from app.services.chunking import chunking_service
from app.models import Timestamp


class TestChunkingService:
    """Test text chunking and embedding generation."""
    
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        text = "This is a test. " * 200  # Create long text
        chunks = chunking_service.chunk_text(text)
        
        assert len(chunks) > 0
        assert all('text' in chunk for chunk in chunks)
        assert all('chunk_index' in chunk for chunk in chunks)
    
    def test_chunk_pdf_by_pages(self):
        """Test PDF page-based chunking."""
        pages = [
            {"page_number": 1, "text": "Page 1 content " * 100},
            {"page_number": 2, "text": "Page 2 content " * 100},
        ]
        
        chunks = chunking_service.chunk_pdf_by_pages(pages, "doc_123")
        
        assert len(chunks) > 0
        assert all('page_number' in chunk['metadata'] for chunk in chunks)
        assert all(chunk['metadata']['document_id'] == "doc_123" for chunk in chunks)
    
    def test_chunk_transcription_with_timestamps(self):
        """Test transcription chunking with timestamps."""
        transcription = "This is a test transcription with multiple segments."
        timestamps = [
            Timestamp(start=0.0, end=5.0, text="This is a test"),
            Timestamp(start=5.0, end=10.0, text="transcription with"),
            Timestamp(start=10.0, end=15.0, text="multiple segments."),
        ]
        
        chunks = chunking_service.chunk_transcription_with_timestamps(
            transcription,
            timestamps,
            "doc_123"
        )
        
        assert len(chunks) > 0
        assert all('timestamps' in chunk['metadata'] for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_generate_embedding(self):
        """Test embedding generation."""
        # Skip test in CI/CD environment
        import os
        api_key = os.getenv('OPENAI_API_KEY', '')
        if not api_key or api_key.startswith('sk-test'):
            pytest.skip("Real OpenAI API key not available")
        
        text = "This is a test sentence for embedding."
        embedding = await chunking_service.generate_embedding(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 1536  # OpenAI embedding dimension


class TestFileValidation:
    """Test file upload validation."""
    
    def test_validate_file_extension(self):
        """Test file extension validation."""
        from app.services.file_upload import FileUploadService
        
        service = FileUploadService()
        
        assert service._validate_file_extension("document.pdf") is True
        assert service._validate_file_extension("audio.mp3") is True
        assert service._validate_file_extension("video.mp4") is True
        assert service._validate_file_extension("invalid.txt") is False
    
    def test_get_file_type(self):
        """Test file type detection."""
        from app.services.file_upload import FileUploadService
        from app.models import FileType
        
        service = FileUploadService()
        
        assert service._get_file_type("application/pdf", "doc.pdf") == FileType.PDF
        assert service._get_file_type("audio/mpeg", "song.mp3") == FileType.AUDIO
        assert service._get_file_type("video/mp4", "video.mp4") == FileType.VIDEO


class TestModels:
    """Test Pydantic models."""
    
    def test_document_metadata_creation(self):
        """Test DocumentMetadata model."""
        from app.models import DocumentMetadata, FileType
        
        metadata = DocumentMetadata(
            file_name="test.pdf",
            file_type=FileType.PDF,
            file_size=1024000,
            mime_type="application/pdf",
            pages=10
        )
        
        assert metadata.file_name == "test.pdf"
        assert metadata.file_type == FileType.PDF
        assert metadata.pages == 10
    
    def test_timestamp_model(self):
        """Test Timestamp model."""
        from app.models import Timestamp
        
        ts = Timestamp(start=0.0, end=5.5, text="Test segment")
        
        assert ts.start == 0.0
        assert ts.end == 5.5
        assert ts.text == "Test segment"
    
    def test_chat_request_validation(self):
        """Test ChatRequest validation."""
        from app.models import ChatRequest
        
        # Valid request
        request = ChatRequest(question="What is this about?")
        assert request.question == "What is this about?"
        assert request.stream is False
        
        # Empty question should fail
        with pytest.raises(Exception):
            ChatRequest(question="")


class TestVectorStore:
    """Test FAISS vector store operations."""
    
    @pytest.mark.asyncio
    async def test_add_and_search_vectors(self):
        """Test adding and searching vectors."""
        from app.services.vector_store import FAISSVectorStore
        import numpy as np
        
        # Create temporary vector store
        store = FAISSVectorStore()
        store._initialize_index()
        
        # Create test embeddings
        embeddings = [
            np.random.randn(1536).tolist() for _ in range(5)
        ]
        metadata = [
            {"chunk_id": f"chunk_{i}", "document_id": "doc_123"}
            for i in range(5)
        ]
        
        # Add vectors
        await store.add_vectors(embeddings, metadata)
        
        assert store.index.ntotal == 5
        
        # Search
        query_embedding = np.random.randn(1536).tolist()
        results = await store.search(query_embedding, top_k=3)
        
        assert len(results) <= 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
