"""
Document processing orchestrator.
Coordinates file upload, extraction, chunking, and embedding generation.
"""
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import (
    FileType, DocumentCreate, Document, ProcessingStatus,
    Chunk, ChunkCreate, ChunkMetadata
)
from app.services.file_upload import file_upload_service
from app.services.pdf_extraction import pdf_extraction_service
from app.services.unified_transcription import get_default_transcription_service
from app.services.chunking import chunking_service
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Orchestrates document processing pipeline."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize processor with database connection."""
        self.db = db
    
    async def process_document(self, document_id: str) -> Document:
        """
        Process uploaded document: extract, chunk, embed.
        
        Args:
            document_id: MongoDB document ID
            
        Returns:
            Updated Document object
        """
        try:
            # Get document from database
            doc_data = await self.db.documents.find_one({"_id": document_id})
            if not doc_data:
                raise ValueError(f"Document not found: {document_id}")
            
            document = Document(**doc_data)
            
            # Update status to processing
            await self.db.documents.update_one(
                {"_id": document_id},
                {"$set": {
                    "status": ProcessingStatus.PROCESSING,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            logger.info(f"Processing document: {document.file_id}")
            
            # Get file path
            file_path = file_upload_service.get_file_path(document.file_path)
            
            # Process based on file type
            if document.metadata.file_type == FileType.PDF:
                await self._process_pdf(document, file_path)
            elif document.metadata.file_type == FileType.AUDIO:
                await self._process_audio(document, file_path)
            elif document.metadata.file_type == FileType.VIDEO:
                await self._process_video(document, file_path)
            else:
                raise ValueError(f"Unsupported file type: {document.metadata.file_type}")
            
            # Update status to completed
            await self.db.documents.update_one(
                {"_id": document_id},
                {"$set": {
                    "status": ProcessingStatus.COMPLETED,
                    "processed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Get updated document
            doc_data = await self.db.documents.find_one({"_id": document_id})
            return Document(**doc_data)
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            
            # Update status to failed
            await self.db.documents.update_one(
                {"_id": document_id},
                {"$set": {
                    "status": ProcessingStatus.FAILED,
                    "error_message": str(e),
                    "updated_at": datetime.utcnow()
                }}
            )
            raise
    
    async def _process_pdf(self, document: Document, file_path: Path):
        """Process PDF document."""
        logger.info(f"Extracting text from PDF: {file_path}")
        
        # Extract text and metadata
        text, pdf_metadata = await pdf_extraction_service.extract_text(file_path)
        
        # Update document with extracted text and metadata
        await self.db.documents.update_one(
            {"_id": document.id},
            {"$set": {
                "extracted_text": text,
                "metadata.pages": pdf_metadata.get("pages", 0),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Extract by pages for better chunking
        pages = await pdf_extraction_service.extract_text_by_pages(file_path)
        
        # Chunk text
        chunks = chunking_service.chunk_pdf_by_pages(pages, document.id)
        
        # Generate embeddings and store
        await self._store_chunks(document.id, chunks, FileType.PDF)
        
        logger.info(f"PDF processing completed: {len(chunks)} chunks created")
    
    async def _process_audio(self, document: Document, file_path: Path):
        """Process audio file."""
        logger.info(f"Transcribing audio: {file_path}")
        
        # Get transcription service
        transcription_service = get_default_transcription_service()
        
        # Transcribe with timestamps
        transcription, timestamps, audio_metadata = await transcription_service.transcribe(
            file_path
        )
        
        # Update document with transcription
        await self.db.documents.update_one(
            {"_id": document.id},
            {"$set": {
                "transcription": transcription,
                "metadata.duration": audio_metadata.get("duration"),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Chunk transcription with timestamps
        chunks = chunking_service.chunk_transcription_with_timestamps(
            transcription,
            timestamps,
            document.id
        )
        
        # Generate embeddings and store
        await self._store_chunks(document.id, chunks, FileType.AUDIO)
        
        logger.info(f"Audio processing completed: {len(chunks)} chunks created")
    
    async def _process_video(self, document: Document, file_path: Path):
        """Process video file."""
        logger.info(f"Processing video: {file_path}")
        
        # Get transcription service
        transcription_service = get_default_transcription_service()
        
        # Extract audio from video
        audio_path = await transcription_service.extract_audio_from_video(file_path)
        
        try:
            # Transcribe audio with timestamps
            transcription, timestamps, audio_metadata = await transcription_service.transcribe(
                audio_path
            )
            
            # Update document with transcription
            await self.db.documents.update_one(
                {"_id": document.id},
                {"$set": {
                    "transcription": transcription,
                    "metadata.duration": audio_metadata.get("duration"),
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Chunk transcription with timestamps
            chunks = chunking_service.chunk_transcription_with_timestamps(
                transcription,
                timestamps,
                document.id
            )
            
            # Generate embeddings and store
            await self._store_chunks(document.id, chunks, FileType.VIDEO)
            
            logger.info(f"Video processing completed: {len(chunks)} chunks created")
            
        finally:
            # Clean up extracted audio
            if audio_path.exists():
                audio_path.unlink()
    
    async def _store_chunks(
        self,
        document_id: str,
        chunks: List[Dict],
        file_type: FileType
    ):
        """Generate embeddings and store chunks."""
        if not chunks:
            logger.warning(f"No chunks to store for document {document_id}")
            return
        
        # Extract chunk texts
        chunk_texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings in batch
        logger.info(f"Generating embeddings for {len(chunk_texts)} chunks")
        embeddings = await chunking_service.generate_embeddings_batch(chunk_texts)
        
        # Prepare chunks for database
        chunk_docs = []
        vector_metadata = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{document_id}_chunk_{i}"
            
            chunk_metadata = ChunkMetadata(
                document_id=document_id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk["metadata"].get("page_number"),
                timestamps=chunk["metadata"].get("timestamps"),
                source_type=file_type
            )
            
            chunk_doc = {
                "_id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "embedding": embedding,
                "metadata": chunk_metadata.dict(),
                "created_at": datetime.utcnow()
            }
            
            chunk_docs.append(chunk_doc)
            
            # Metadata for vector store
            vector_metadata.append({
                "chunk_id": chunk_id,
                "document_id": document_id,
                "chunk_index": chunk["chunk_index"],
                "page_number": chunk_metadata.page_number,
                "has_timestamps": chunk_metadata.timestamps is not None
            })
        
        # Store chunks in MongoDB
        if chunk_docs:
            await self.db.chunks.insert_many(chunk_docs)
            logger.info(f"Stored {len(chunk_docs)} chunks in MongoDB")
        
        # Store embeddings in vector store
        await vector_store.add_vectors(embeddings, vector_metadata)
        vector_store.save_index()
        logger.info(f"Stored {len(embeddings)} embeddings in FAISS")
        
        # Update document chunk count
        await self.db.documents.update_one(
            {"_id": document_id},
            {"$set": {
                "chunk_count": len(chunk_docs),
                "updated_at": datetime.utcnow()
            }}
        )
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document and all associated data."""
        try:
            # Get document
            doc_data = await self.db.documents.find_one({"_id": document_id})
            if not doc_data:
                return False
            
            document = Document(**doc_data)
            
            # Delete file from storage
            await file_upload_service.delete_file(document.file_path)
            
            # Delete chunks from database
            await self.db.chunks.delete_many({"document_id": document_id})
            
            # Delete vectors from vector store
            await vector_store.delete_by_document_id(document_id)
            vector_store.save_index()
            
            # Delete document from database
            await self.db.documents.delete_one({"_id": document_id})
            
            logger.info(f"Document deleted: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise
