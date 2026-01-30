"""
RAG (Retrieval-Augmented Generation) chatbot service using LangChain and OpenAI.
Provides context-aware Q&A from uploaded documents.
"""
import logging
from typing import List, Optional, Dict, AsyncGenerator
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from app.core.config import settings
from app.models import (
    ChatRequest, ChatResponse, SourceReference,
    ChatMessage, Timestamp
)
from app.services.chunking import chunking_service
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)


class RAGChatService:
    """RAG-based chatbot service."""
    
    SYSTEM_PROMPT = """You are an intelligent Q&A assistant. Your task is to answer questions based ONLY on the provided context from uploaded documents.

Rules:
1. Answer questions using ONLY information from the provided context
2. If the answer is not in the context, say "I don't have enough information to answer that question based on the uploaded documents."
3. Be concise and accurate
4. When referencing audio/video content, mention the timestamp
5. Cite which document the information comes from
6. If multiple documents contain relevant information, synthesize the answer

Context will be provided with each question."""
    
    def __init__(self, db: AsyncIOMotorDatabase, user_id: Optional[str] = None):
        """Initialize RAG chat service.
        
        Args:
            db: MongoDB database instance
            user_id: Optional user ID for filtering documents
        """
        self.db = db
        self.user_id = user_id
        
        # Check if we should use free LLM
        if settings.USE_FREE_LLM:
            logger.info("Using free local LLM (google/flan-t5-base)")
            from app.services.free_llm import free_llm_service
            self.llm = None
            self.free_llm = free_llm_service
        else:
            self.llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.3,
                streaming=True
            )
            self.free_llm = None
    
    async def chat(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        """
        Process chat request and return answer.
        
        Args:
            request: Chat request with question and filters
            
        Returns:
            Chat response with answer and sources
        """
        try:
            logger.info(f"Processing chat request: {request.question[:50]}...")
            
            # Generate embedding for question
            query_embedding = await chunking_service.generate_embedding(
                request.question
            )
            
            # Search for relevant chunks
            filter_meta = {}
            if request.document_ids:
                # We'll filter after retrieval since FAISS metadata filtering is limited
                pass
            
            search_results = await vector_store.search(
                query_embedding=query_embedding,
                top_k=5
            )
            
            # Get full chunk details from database
            relevant_chunks = await self._get_chunk_details(
                search_results,
                request.document_ids
            )
            
            if not relevant_chunks:
                return ChatResponse(
                    answer="I don't have any relevant information to answer your question. Please upload relevant documents first.",
                    sources=[]
                )
            
            # Build context from chunks
            context = await self._build_context(relevant_chunks)
            
            # Generate answer based on LLM type
            if self.free_llm:
                # Use free local LLM
                logger.info("Using free local LLM for response generation")
                # Convert ChatMessage objects to dicts for free LLM
                history_dicts = None
                if request.conversation_history:
                    history_dicts = [
                        {
                            "is_user": msg.role == "user",
                            "content": msg.content
                        }
                        for msg in request.conversation_history
                    ]
                answer = self.free_llm.chat(
                    question=request.question,
                    context=context,
                    conversation_history=history_dicts
                )
            else:
                # Use OpenAI
                messages = self._build_messages(
                    request.question,
                    context,
                    request.conversation_history
                )
                response = await self.llm.ainvoke(messages)
                answer = response.content
            
            # Build source references
            sources = await self._build_sources(relevant_chunks)
            
            logger.info(f"Chat response generated with {len(sources)} sources")
            
            return ChatResponse(
                answer=answer,
                sources=sources
            )
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}")
            raise
    
    async def chat_stream(
        self,
        request: ChatRequest
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response token by token.
        
        Yields:
            Text chunks as they are generated
        """
        try:
            logger.info(f"Processing streaming chat request: {request.question[:50]}...")
            
            # Generate embedding and search (same as non-streaming)
            query_embedding = await chunking_service.generate_embedding(
                request.question
            )
            
            search_results = await vector_store.search(
                query_embedding=query_embedding,
                top_k=5
            )
            
            relevant_chunks = await self._get_chunk_details(
                search_results,
                request.document_ids
            )
            
            if not relevant_chunks:
                yield "I don't have any relevant information to answer your question. Please upload relevant documents first."
                return
            
            # Build context
            context = await self._build_context(relevant_chunks)
            
            # Check if we're using free LLM (doesn't support native streaming)
            if self.free_llm:
                # Free LLM generates full response, simulate streaming
                import asyncio
                history_dicts = None
                if request.conversation_history:
                    history_dicts = [
                        {
                            "is_user": msg.role == "user",
                            "content": msg.content
                        }
                        for msg in request.conversation_history
                    ]
                answer = self.free_llm.chat(
                    question=request.question,
                    context=context,
                    conversation_history=history_dicts
                )
                
                # Simulate streaming by yielding words progressively
                words = answer.split()
                for i, word in enumerate(words):
                    if i < len(words) - 1:
                        yield word + " "
                    else:
                        yield word
                    await asyncio.sleep(0.05)  # Small delay for smooth streaming effect
            else:
                # OpenAI LLM supports native streaming
                messages = self._build_messages(
                    request.question,
                    context,
                    request.conversation_history
                )
                
                # Stream response
                async for chunk in self.llm.astream(messages):
                    if chunk.content:
                        yield chunk.content
            
        except Exception as e:
            logger.error(f"Streaming chat failed: {e}")
            yield f"Error: {str(e)}"
    
    async def _get_chunk_details(
        self,
        search_results: List[tuple],
        document_ids: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get full chunk details from database, filtering by user_id if set."""
        chunks = []
        
        for metadata, score in search_results:
            chunk_id = metadata.get("chunk_id")
            
            # Filter by document IDs if specified
            if document_ids and metadata.get("document_id") not in document_ids:
                continue
            
            # Get chunk from database
            chunk_data = await self.db.chunks.find_one({"_id": chunk_id})
            if not chunk_data:
                continue
            
            # Verify document ownership if user_id is set
            if self.user_id:
                doc = await self.db.documents.find_one({"_id": chunk_data["document_id"]})
                if not doc or doc.get("user_id") != self.user_id:
                    continue
            
            chunk_data["relevance_score"] = score
            chunks.append(chunk_data)
        
        return chunks
    
    async def _build_context(self, chunks: List[Dict]) -> str:
        """Build context string from chunks."""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            # Get document info
            doc_data = await self.db.documents.find_one(
                {"_id": chunk["document_id"]}
            )
            
            if not doc_data:
                continue
            
            doc_name = doc_data["metadata"]["file_name"]
            context_part = f"[Source {i}: {doc_name}"
            
            # Add page number if available
            if chunk["metadata"].get("page_number"):
                context_part += f", Page {chunk['metadata']['page_number']}"
            
            # Add timestamps if available
            if chunk["metadata"].get("timestamps"):
                timestamps = chunk["metadata"]["timestamps"]
                if timestamps:
                    start_time = timestamps[0]["start"]
                    context_part += f", Timestamp: {self._format_timestamp(start_time)}"
            
            context_part += "]\n" + chunk["text"] + "\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _build_messages(
        self,
        question: str,
        context: str,
        history: Optional[List[ChatMessage]] = None
    ) -> List:
        """Build message list for LLM."""
        messages = [SystemMessage(content=self.SYSTEM_PROMPT)]
        
        # Add conversation history
        if history:
            for msg in history[-5:]:  # Last 5 messages
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        
        # Add current question with context
        user_message = f"""Context from uploaded documents:
{context}

Question: {question}

Answer based only on the context above:"""
        
        messages.append(HumanMessage(content=user_message))
        
        return messages
    
    async def _build_sources(self, chunks: List[Dict]) -> List[SourceReference]:
        """Build source references from chunks."""
        sources = []
        
        for chunk in chunks:
            # Get document info
            doc_data = await self.db.documents.find_one(
                {"_id": chunk["document_id"]}
            )
            
            if not doc_data:
                continue
            
            # Build timestamps list
            timestamps = None
            if chunk["metadata"].get("timestamps"):
                timestamps = [
                    Timestamp(**ts) for ts in chunk["metadata"]["timestamps"]
                ]
            
            source = SourceReference(
                document_id=chunk["document_id"],
                document_name=doc_data["metadata"]["file_name"],
                chunk_text=chunk["text"][:200] + "...",  # Truncate for preview
                page_number=chunk["metadata"].get("page_number"),
                timestamps=timestamps,
                relevance_score=chunk.get("relevance_score", 0.0)
            )
            
            sources.append(source)
        
        return sources
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    async def summarize_document(
        self,
        document_id: str,
        max_length: int = 500
    ) -> str:
        """
        Generate summary of a document.
        
        Args:
            document_id: Document ID to summarize
            max_length: Maximum summary length in words
            
        Returns:
            Summary text
        """
        try:
            # Get document
            doc_data = await self.db.documents.find_one({"_id": document_id})
            if not doc_data:
                raise ValueError(f"Document not found: {document_id}")
            
            # Get content
            content = doc_data.get("extracted_text") or doc_data.get("transcription")
            if not content:
                raise ValueError("No content available to summarize")
            
            # Truncate if too long (to fit in context window)
            if len(content) > 10000:
                content = content[:10000] + "..."
            
            # Create summary prompt
            prompt = f"""Summarize the following document in approximately {max_length} words. Focus on the main points and key information.

Document: {doc_data['metadata']['file_name']}

Content:
{content}

Summary:"""
            
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            summary = response.content
            
            # Update document with summary
            await self.db.documents.update_one(
                {"_id": document_id},
                {"$set": {
                    "summary": summary,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            logger.info(f"Generated summary for document {document_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise
