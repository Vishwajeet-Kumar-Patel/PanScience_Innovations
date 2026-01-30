"""
Document management API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.auth import User
from app.models import Document, DocumentResponse, ProcessingStatus, SummaryRequest, SummaryResponse
from app.services.document_processor import DocumentProcessor
from app.services.rag_chat import RAGChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[ProcessingStatus] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all uploaded documents with pagination.
    Requires authentication. Users can only see their own documents.
    
    Query parameters:
    - skip: Number of documents to skip (for pagination)
    - limit: Maximum number of documents to return
    - status_filter: Filter by processing status
    """
    try:
        # Build query - filter by user_id
        query = {"user_id": current_user.id}
        if status_filter:
            query["status"] = status_filter.value
        
        # Get documents
        cursor = db.documents.find(query).sort("created_at", -1).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)
        
        # Convert to response format
        responses = []
        for doc in documents:
            responses.append(DocumentResponse(
                id=doc["_id"],
                file_id=doc["file_id"],
                file_name=doc["metadata"]["file_name"],
                file_path=doc["file_path"],
                file_type=doc["metadata"]["file_type"],
                file_size=doc["metadata"]["file_size"],
                status=doc["status"],
                created_at=doc["created_at"],
                chunk_count=doc.get("chunk_count", 0),
                summary=doc.get("summary")
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get detailed information about a specific document.
    Requires authentication. Users can only access their own documents.
    """
    try:
        doc_data = await db.documents.find_one({"_id": document_id})
        
        if not doc_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Verify ownership
        if doc_data.get("user_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this document"
            )
        
        return Document(**doc_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a document and all associated data (chunks, embeddings).
    Requires authentication. Users can only delete their own documents.
    """
    try:
        # Check ownership first
        doc_data = await db.documents.find_one({"_id": document_id})
        
        if not doc_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Verify ownership
        if doc_data.get("user_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this document"
            )
        
        processor = DocumentProcessor(db)
        success = await processor.delete_document(document_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.post("/{document_id}/summarize", response_model=SummaryResponse)
async def summarize_document(
    document_id: str,
    request: SummaryRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a summary of a document using AI.
    Requires authentication. Users can only summarize their own documents.
    
    The summary will be cached in the document for future requests.
    """
    try:
        # Check if document exists
        doc_data = await db.documents.find_one({"_id": document_id})
        if not doc_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Verify ownership
        if doc_data.get("user_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to summarize this document"
            )
        
        # Check if already has summary
        if doc_data.get("summary"):
            return SummaryResponse(
                document_id=document_id,
                summary=doc_data["summary"],
                word_count=len(doc_data["summary"].split())
            )
        
        # Generate summary
        chat_service = RAGChatService(db)
        summary = await chat_service.summarize_document(
            document_id,
            request.max_length
        )
        
        return SummaryResponse(
            document_id=document_id,
            summary=summary,
            word_count=len(summary.split())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to summarize document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary"
        )


@router.get("/stats/overview")
async def get_stats(db: AsyncIOMotorDatabase = Depends(get_db)):
    """
    Get overall statistics about uploaded documents.
    """
    try:
        total_docs = await db.documents.count_documents({})
        
        # Count by status
        status_counts = {}
        for status_val in ProcessingStatus:
            count = await db.documents.count_documents({"status": status_val.value})
            status_counts[status_val.value] = count
        
        # Count by type
        pipeline = [
            {"$group": {
                "_id": "$metadata.file_type",
                "count": {"$sum": 1}
            }}
        ]
        type_counts = {}
        async for result in db.documents.aggregate(pipeline):
            type_counts[result["_id"]] = result["count"]
        
        # Total chunks
        total_chunks = await db.chunks.count_documents({})
        
        return {
            "total_documents": total_docs,
            "status_counts": status_counts,
            "type_counts": type_counts,
            "total_chunks": total_chunks
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )
