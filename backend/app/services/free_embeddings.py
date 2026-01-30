"""
Free embedding service using Sentence Transformers (no API costs).
Runs locally without requiring any API keys.
"""
import logging
from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class FreeEmbeddingService:
    """Service for generating embeddings using free Sentence Transformers."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding service with a free model.
        
        Args:
            model_name: Name of the sentence-transformers model
                       Default: all-MiniLM-L6-v2 (384 dimensions, fast, good quality)
                       Alternatives: all-mpnet-base-v2 (768 dim, slower, better quality)
        """
        logger.info(f"Loading free embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.dimension}")
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts")
        
        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True  # Normalize for cosine similarity
        )
        
        # Convert to list of lists
        embeddings_list = embeddings.tolist()
        
        logger.info(f"Generated {len(embeddings_list)} embeddings")
        return embeddings_list
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        Generate embeddings in batches (async wrapper for compatibility).
        
        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process at once
            
        Returns:
            List of embedding vectors
        """
        # Sentence transformers is synchronous, but we wrap it for compatibility
        return self.generate_embeddings(texts)


# Singleton instance
_embedding_service = None


def get_embedding_service() -> FreeEmbeddingService:
    """Get or create singleton embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = FreeEmbeddingService()
    return _embedding_service
