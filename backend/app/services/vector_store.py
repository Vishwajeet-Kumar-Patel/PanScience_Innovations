"""
Vector store service using FAISS for semantic search.
Manages embeddings and similarity search operations.
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pickle
import numpy as np
import faiss
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """FAISS-based vector store for similarity search."""
    
    def __init__(self):
        """Initialize FAISS vector store."""
        self.index: Optional[faiss.Index] = None
        
        # Set dimension based on embedding service
        if settings.USE_FREE_EMBEDDINGS:
            self.dimension = 384  # sentence-transformers all-MiniLM-L6-v2 dimension
        else:
            self.dimension = 1536  # OpenAI text-embedding-3-small dimension
            
        self.index_path = Path(settings.FAISS_INDEX_PATH)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Metadata storage (maps index position to document/chunk info)
        self.metadata: List[Dict] = []
        
        # Load existing index if available
        self._load_index()
    
    def _load_index(self):
        """Load existing FAISS index from disk."""
        index_file = self.index_path / "index.faiss"
        metadata_file = self.index_path / "metadata.pkl"
        
        if index_file.exists() and metadata_file.exists():
            try:
                self.index = faiss.read_index(str(index_file))
                with open(metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                
                logger.info(
                    f"Loaded FAISS index with {self.index.ntotal} vectors, dimension={self.index.d}"
                )
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                self._initialize_index()
        else:
            self._initialize_index()
    
    def _initialize_index(self):
        """Initialize a new FAISS index."""
        # Use IndexFlatIP for cosine similarity (inner product)
        # We'll normalize vectors before adding them
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
        logger.info(f"Initialized new FAISS index with dimension {self.dimension}, index.d={self.index.d}")
    
    def save_index(self):
        """Save FAISS index to disk."""
        try:
            index_file = self.index_path / "index.faiss"
            metadata_file = self.index_path / "metadata.pkl"
            
            faiss.write_index(self.index, str(index_file))
            
            with open(metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise
    
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector for cosine similarity."""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm
    
    async def add_vectors(
        self,
        embeddings: List[List[float]],
        metadata: List[Dict]
    ):
        """
        Add vectors to the index.
        
        Args:
            embeddings: List of embedding vectors
            metadata: List of metadata dicts (one per embedding)
        """
        if not embeddings or not metadata:
            logger.warning("No embeddings or metadata to add")
            return
        
        if len(embeddings) != len(metadata):
            raise ValueError("Number of embeddings must match number of metadata entries")
        
        try:
            logger.info(f"Converting {len(embeddings)} embeddings to numpy array")
            logger.info(f"First embedding shape: {len(embeddings[0])}")
            
            # Convert to numpy array and normalize
            vectors = np.array(embeddings, dtype=np.float32)
            logger.info(f"Numpy array shape: {vectors.shape}, dtype: {vectors.dtype}")
            logger.info(f"Expected dimension: {self.dimension}, actual dimension: {vectors.shape[1]}")
            
            if vectors.shape[1] != self.dimension:
                raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}")
            
            logger.info("Normalizing vectors")
            vectors = np.apply_along_axis(self._normalize_vector, 1, vectors)
            logger.info(f"Vectors normalized, shape: {vectors.shape}")
            
            # Add to index
            logger.info(f"Adding {len(vectors)} vectors to FAISS index (current total: {self.index.ntotal})")
            logger.info(f"FAISS index dimension: {self.index.d}, vector dimension: {vectors.shape[1]}")
            self.index.add(vectors)
            logger.info(f"Vectors added successfully. New total: {self.index.ntotal}")
            
            # Add metadata
            self.metadata.extend(metadata)
            
            logger.info(f"Added {len(embeddings)} vectors to index")
            
            # Save periodically
            if self.index.ntotal % 100 == 0:
                self.save_index()
            
        except Exception as e:
            logger.error(f"Failed to add vectors: {str(e)}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error args: {e.args}")
            raise
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Tuple[Dict, float]]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"document_id": "123"})
            
        Returns:
            List of (metadata, similarity_score) tuples
        """
        if self.index.ntotal == 0:
            logger.warning("Index is empty, cannot search")
            return []
        
        try:
            # Normalize query vector
            query_vector = np.array([query_embedding], dtype=np.float32)
            query_vector = np.apply_along_axis(
                self._normalize_vector, 1, query_vector
            )
            
            # Search
            # Get more results if filtering is needed
            search_k = top_k * 3 if filter_metadata else top_k
            distances, indices = self.index.search(query_vector, search_k)
            
            # Collect results
            results = []
            for i, idx in enumerate(indices[0]):
                if idx == -1:  # FAISS returns -1 for missing results
                    continue
                
                meta = self.metadata[idx]
                score = float(distances[0][i])
                
                # Apply filters
                if filter_metadata:
                    match = all(
                        meta.get(k) == v
                        for k, v in filter_metadata.items()
                    )
                    if not match:
                        continue
                
                results.append((meta, score))
                
                if len(results) >= top_k:
                    break
            
            logger.info(f"Found {len(results)} similar vectors")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    async def delete_by_document_id(self, document_id: str):
        """
        Delete all vectors for a document.
        
        Note: FAISS doesn't support deletion, so we rebuild the index.
        """
        try:
            # Find indices to keep
            indices_to_keep = [
                i for i, meta in enumerate(self.metadata)
                if meta.get("document_id") != document_id
            ]
            
            if len(indices_to_keep) == len(self.metadata):
                logger.info(f"No vectors found for document {document_id}")
                return
            
            # Rebuild index with remaining vectors
            logger.info(f"Rebuilding index after deleting document {document_id}")
            
            # Get vectors to keep (reconstruct from index)
            vectors_to_keep = []
            metadata_to_keep = []
            
            for idx in indices_to_keep:
                # Reconstruct vector from index
                vector = self.index.reconstruct(idx)
                vectors_to_keep.append(vector)
                metadata_to_keep.append(self.metadata[idx])
            
            # Reinitialize and add vectors
            self._initialize_index()
            if vectors_to_keep:
                vectors_array = np.array(vectors_to_keep, dtype=np.float32)
                self.index.add(vectors_array)
                self.metadata = metadata_to_keep
            
            self.save_index()
            logger.info(f"Index rebuilt with {self.index.ntotal} vectors")
            
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            raise
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "index_type": "FAISS IndexFlatIP",
            "storage_path": str(self.index_path),
        }


# Singleton instance
vector_store = FAISSVectorStore()
