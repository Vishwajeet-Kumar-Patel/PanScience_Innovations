"""
Chat API endpoints for Q&A with streaming support.
"""
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
import json

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.auth import User
from app.models import ChatRequest, ChatResponse, SearchRequest, SearchResponse, SearchResult
from app.services.rag_chat import RAGChatService
from app.services.chunking import chunking_service
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Ask a question about uploaded documents.
    Requires authentication. Users can only chat with their own documents.
    
    The system will search for relevant content across all uploaded documents
    and provide an answer based only on that content.
    
    - **question**: Your question
    - **document_ids**: Optional list of specific document IDs to search
    - **conversation_history**: Optional previous messages for context
    """
    try:
        # Verify document ownership if document_ids provided
        if request.document_ids:
            for doc_id in request.document_ids:
                doc = await db.documents.find_one({"_id": doc_id})
                if not doc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document not found: {doc_id}"
                    )
                if doc.get("user_id") != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to access one or more documents"
                    )
        
        chat_service = RAGChatService(db, user_id=current_user.id)
        response = await chat_service.chat(request)
        return response
        
    except Exception as e:
        logger.error(f"Chat request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Ask a question with streaming response.
    Requires authentication. Users can only chat with their own documents.
    
    The response will be streamed token by token as it's generated,
    providing a more interactive experience.
    
    Returns: text/event-stream with incremental response chunks
    """
    try:
        # Verify document ownership if document_ids provided
        if request.document_ids:
            for doc_id in request.document_ids:
                doc = await db.documents.find_one({"_id": doc_id})
                if not doc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document not found: {doc_id}"
                    )
                if doc.get("user_id") != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to access one or more documents"
                    )
        
        chat_service = RAGChatService(db, user_id=current_user.id)
        
        async def generate():
            """Generate streaming response."""
            try:
                async for chunk in chat_service.chat_stream(request):
                    # Send as server-sent events
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                # Send done signal
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except Exception as e:
        logger.error(f"Stream initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming failed: {str(e)}"
        )


@router.post("/search", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Perform semantic search across uploaded documents.
    Requires authentication. Users can only search their own documents.
    
    Returns the most relevant text chunks without generating an answer.
    Useful for finding specific information or exploring document content.
    
    - **query**: Search query
    - **document_ids**: Optional list of specific document IDs to search
    - **top_k**: Number of results to return (1-20)
    """
    try:
        # Verify document ownership if document_ids provided
        if request.document_ids:
            for doc_id in request.document_ids:
                doc = await db.documents.find_one({"_id": doc_id})
                if not doc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document not found: {doc_id}"
                    )
                if doc.get("user_id") != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You do not have permission to access one or more documents"
                    )
        
        # Generate query embedding
        query_embedding = await chunking_service.generate_embedding(request.query)
        
        # Search vector store
        search_results = await vector_store.search(
            query_embedding=query_embedding,
            top_k=request.top_k
        )
        
        # Get chunk details
        results = []
        for metadata, score in search_results:
            chunk_id = metadata.get("chunk_id")
            
            # Filter by document IDs if specified
            if request.document_ids and metadata.get("document_id") not in request.document_ids:
                continue
            
            # Get full chunk data
            chunk_data = await db.chunks.find_one({"_id": chunk_id})
            if not chunk_data:
                continue
            
            # Get document name
            doc_data = await db.documents.find_one({"_id": chunk_data["document_id"]})
            if not doc_data:
                continue
            
            # Build timestamps if available
            timestamps = None
            if chunk_data["metadata"].get("timestamps"):
                from app.models import Timestamp
                timestamps = [
                    Timestamp(**ts) for ts in chunk_data["metadata"]["timestamps"]
                ]
            
            result = SearchResult(
                document_id=chunk_data["document_id"],
                document_name=doc_data["metadata"]["file_name"],
                chunk_text=chunk_data["text"],
                score=score,
                page_number=chunk_data["metadata"].get("page_number"),
                timestamps=timestamps
            )
            
            results.append(result)
        
        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results)
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get recent chat history.
    
    Note: This is a placeholder. In production, you'd want to:
    - Store conversations in the database
    - Associate with user sessions
    - Implement proper pagination
    """
    # TODO: Implement conversation storage and retrieval
    return {
        "message": "Chat history feature coming soon",
        "conversations": []
    }
