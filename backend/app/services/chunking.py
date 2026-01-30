"""
Text chunking and embedding service.
Splits text into chunks and generates embeddings using OpenAI.
"""
import logging
from typing import List, Dict, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
import numpy as np

from app.core.config import settings
from app.models import Timestamp

logger = logging.getLogger(__name__)
# Import free embedding service
try:
    from app.services.free_embeddings import get_embedding_service as get_free_embedding_service
    FREE_EMBEDDINGS_AVAILABLE = True
except ImportError:
    FREE_EMBEDDINGS_AVAILABLE = False
    logger.warning("Free embeddings not available")

class ChunkingService:
    """Service for chunking text and generating embeddings."""
    
    def __init__(self):
        """Initialize chunking service."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Split text into chunks.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk
            
        Returns:
            List of chunk dictionaries
        """
        try:
            # Split text
            chunks = self.text_splitter.split_text(text)
            
            # Create chunk objects
            chunk_objects = []
            for i, chunk_text in enumerate(chunks):
                chunk_obj = {
                    "chunk_index": i,
                    "text": chunk_text,
                    "metadata": metadata or {}
                }
                chunk_objects.append(chunk_obj)
            
            logger.info(f"Created {len(chunk_objects)} chunks from text")
            return chunk_objects
            
        except Exception as e:
            logger.error(f"Text chunking failed: {e}")
            raise
    
    def chunk_pdf_by_pages(
        self,
        pages: List[Dict],
        document_id: str
    ) -> List[Dict]:
        """
        Chunk PDF text page by page.
        
        Args:
            pages: List of page dicts with page_number and text
            document_id: ID of the document
            
        Returns:
            List of chunks with page metadata
        """
        all_chunks = []
        chunk_index = 0
        
        for page in pages:
            page_num = page["page_number"]
            page_text = page["text"]
            
            # Split page text
            page_chunks = self.text_splitter.split_text(page_text)
            
            for chunk_text in page_chunks:
                chunk = {
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "metadata": {
                        "document_id": document_id,
                        "page_number": page_num,
                    }
                }
                all_chunks.append(chunk)
                chunk_index += 1
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(pages)} pages")
        return all_chunks
    
    def chunk_transcription_with_timestamps(
        self,
        transcription: str,
        timestamps: List[Timestamp],
        document_id: str
    ) -> List[Dict]:
        """
        Chunk transcription while preserving timestamp information.
        
        Args:
            transcription: Full transcription text
            timestamps: List of timestamp segments
            document_id: ID of the document
            
        Returns:
            List of chunks with timestamp metadata
        """
        all_chunks = []
        chunk_index = 0
        
        # Group timestamp segments into chunks
        current_chunk_text = []
        current_timestamps = []
        current_length = 0
        
        for ts in timestamps:
            segment_text = ts.text
            segment_length = len(segment_text)
            
            # Check if adding this segment exceeds chunk size
            if current_length + segment_length > settings.CHUNK_SIZE and current_chunk_text:
                # Create chunk from accumulated segments
                chunk = {
                    "chunk_index": chunk_index,
                    "text": " ".join(current_chunk_text),
                    "metadata": {
                        "document_id": document_id,
                        "timestamps": [ts.dict() for ts in current_timestamps],
                    }
                }
                all_chunks.append(chunk)
                chunk_index += 1
                
                # Reset accumulators
                current_chunk_text = []
                current_timestamps = []
                current_length = 0
            
            # Add segment to current chunk
            current_chunk_text.append(segment_text)
            current_timestamps.append(ts)
            current_length += segment_length
        
        # Add remaining segments as final chunk
        if current_chunk_text:
            chunk = {
                "chunk_index": chunk_index,
                "text": " ".join(current_chunk_text),
                "metadata": {
                    "document_id": document_id,
                    "timestamps": [ts.dict() for ts in current_timestamps],
                }
            }
            all_chunks.append(chunk)
        
        logger.info(
            f"Created {len(all_chunks)} chunks from {len(timestamps)} "
            f"timestamp segments"
        )
        return all_chunks
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI or free embeddings.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            # Check if we should use free embeddings
            if settings.USE_FREE_EMBEDDINGS:
                logger.info("Using free local embeddings (sentence-transformers)")
                from app.services.free_embeddings import get_embedding_service
                free_service = get_embedding_service()
                embeddings = free_service.generate_embeddings([text])
                return embeddings[0]
            
            response = await self.client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            
        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        
        try:
            # Check if we should use free embeddings
            if settings.USE_FREE_EMBEDDINGS and FREE_EMBEDDINGS_AVAILABLE:
                logger.info("Using free local embeddings (sentence-transformers)")
                free_service = get_free_embedding_service()
                all_embeddings = free_service.generate_embeddings(texts)
                logger.info(f"Generated {len(all_embeddings)} embeddings using free service")
                return all_embeddings
            
            # Otherwise use OpenAI
            logger.info("Using OpenAI embeddings")
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = await self.client.embeddings.create(
                    model=settings.OPENAI_EMBEDDING_MODEL,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.info(f"Generated embeddings for batch {i//batch_size + 1}")
            
            logger.info(f"Generated {len(all_embeddings)} embeddings total")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise


# Singleton instance
chunking_service = ChunkingService()
