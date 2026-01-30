"""
Pydantic models for data validation and serialization.
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class FileType(str, Enum):
    """Supported file types."""
    PDF = "pdf"
    AUDIO = "audio"
    VIDEO = "video"


class ProcessingStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============= Document Models =============

class DocumentMetadata(BaseModel):
    """Metadata for uploaded documents."""
    file_name: str
    file_type: FileType
    file_size: int  # bytes
    mime_type: str
    duration: Optional[float] = None  # seconds, for audio/video
    pages: Optional[int] = None  # for PDFs
    language: Optional[str] = "en"
    
    model_config = ConfigDict(use_enum_values=True)


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""
    file_name: str
    file_type: FileType
    file_path: str
    metadata: DocumentMetadata
    user_id: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


class Document(BaseModel):
    """Document model stored in database."""
    id: str = Field(alias="_id")
    file_id: str
    file_path: str
    metadata: DocumentMetadata
    status: ProcessingStatus = ProcessingStatus.PENDING
    user_id: Optional[str] = None
    
    # Content
    extracted_text: Optional[str] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # Processing info
    error_message: Optional[str] = None
    chunk_count: int = 0
    
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "file_id": "unique-file-id-123",
                "file_path": "/uploads/document.pdf",
                "metadata": {
                    "file_name": "research_paper.pdf",
                    "file_type": "pdf",
                    "file_size": 2048576,
                    "mime_type": "application/pdf",
                    "pages": 15
                },
                "status": "completed",
                "extracted_text": "Document content...",
                "chunk_count": 25
            }
        }
    )


class DocumentResponse(BaseModel):
    """Response model for document queries."""
    id: str
    file_id: str
    file_name: str
    file_path: str
    file_type: FileType
    file_size: int
    status: ProcessingStatus
    created_at: datetime
    chunk_count: int
    summary: Optional[str] = None
    
    model_config = ConfigDict(use_enum_values=True)


# ============= Chunk Models =============

class Timestamp(BaseModel):
    """Timestamp reference for audio/video chunks."""
    start: float  # seconds
    end: float  # seconds
    text: str


class ChunkMetadata(BaseModel):
    """Metadata for text chunks."""
    document_id: str
    chunk_index: int
    page_number: Optional[int] = None  # for PDFs
    timestamps: Optional[List[Timestamp]] = None  # for audio/video
    source_type: FileType


class Chunk(BaseModel):
    """Text chunk with embeddings."""
    id: str = Field(alias="_id")
    document_id: str
    chunk_index: int
    text: str
    embedding: Optional[List[float]] = None
    metadata: ChunkMetadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


class ChunkCreate(BaseModel):
    """Schema for creating chunks."""
    document_id: str
    chunk_index: int
    text: str
    metadata: ChunkMetadata


# ============= Chat Models =============

class ChatMessage(BaseModel):
    """Single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """Request for chat completion."""
    question: str = Field(..., min_length=1, max_length=2000)
    document_ids: Optional[List[str]] = None  # Filter by specific documents
    conversation_history: Optional[List[ChatMessage]] = []
    stream: bool = False
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What is the main topic of the uploaded document?",
                "document_ids": ["507f1f77bcf86cd799439011"],
                "stream": True
            }
        }
    )


class SourceReference(BaseModel):
    """Reference to source document for answer."""
    document_id: str
    document_name: str
    chunk_text: str
    page_number: Optional[int] = None
    timestamps: Optional[List[Timestamp]] = None
    relevance_score: float


class ChatResponse(BaseModel):
    """Response from chat completion."""
    answer: str
    sources: List[SourceReference]
    conversation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============= User Models (for Auth) =============

class UserRole(str, Enum):
    """User roles."""
    USER = "user"
    ADMIN = "admin"


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str


class User(BaseModel):
    """User model."""
    id: str = Field(alias="_id")
    email: EmailStr
    hashed_password: str
    full_name: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


class UserResponse(BaseModel):
    """Public user information."""
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(use_enum_values=True)


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    exp: datetime


# ============= Summary Models =============

class SummaryRequest(BaseModel):
    """Request for document summarization."""
    document_id: str
    max_length: Optional[int] = Field(default=500, ge=100, le=2000)


class SummaryResponse(BaseModel):
    """Summary response."""
    document_id: str
    summary: str
    word_count: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ============= Search Models =============

class SearchRequest(BaseModel):
    """Request for semantic search."""
    query: str = Field(..., min_length=1, max_length=500)
    document_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    """Single search result."""
    document_id: str
    document_name: str
    chunk_text: str
    score: float
    page_number: Optional[int] = None
    timestamps: Optional[List[Timestamp]] = None


class SearchResponse(BaseModel):
    """Search results response."""
    results: List[SearchResult]
    query: str
    total_results: int
