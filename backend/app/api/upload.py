"""
Upload API endpoints for document, audio, and video files.
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, BackgroundTasks
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.auth import User
from app.models import DocumentCreate, DocumentResponse, ProcessingStatus
from app.services.file_upload import file_upload_service
from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])


async def process_document_background(document_id: str, db: AsyncIOMotorDatabase):
    """Background task for document processing."""
    try:
        processor = DocumentProcessor(db)
        await processor.process_document(document_id)
    except Exception as e:
        logger.error(f"Background processing failed for {document_id}: {e}")


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a document, audio, or video file.
    
    Requires authentication. Users can only access their own uploaded files.
    
    Supported formats:
    - PDF documents
    - Audio: MP3, WAV, M4A
    - Video: MP4, AVI, MOV
    
    The file will be processed asynchronously to extract content and generate embeddings.
    """
    try:
        logger.info(f"User {current_user.email} uploading file: {file.filename}")
        
        # Validate file
        file_type, mime_type = await file_upload_service.validate_file(file)
        
        # Save file
        file_id, file_path, file_size = await file_upload_service.save_file(
            file, file_type
        )
        
        # Create metadata
        metadata = await file_upload_service.create_metadata(
            file.filename,
            file_type,
            file_size,
            mime_type
        )
        
        # Create document record
        document_data = {
            "_id": file_id,
            "file_id": file_id,
            "file_path": file_path,
            "user_id": current_user.id,  # Associate document with user
            "metadata": metadata.dict(),
            "status": ProcessingStatus.PENDING,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "chunk_count": 0
        }
        
        # Insert into database
        await db.documents.insert_one(document_data)
        
        logger.info(f"Document created: {file_id}")
        
        # Trigger background processing
        background_tasks.add_task(
            process_document_background,
            file_id,
            db
        )
        
        # Return response
        return DocumentResponse(
            id=file_id,
            file_id=file_id,
            file_name=file.filename,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            status=ProcessingStatus.PENDING,
            created_at=document_data["created_at"],
            chunk_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.post("/batch", response_model=list[DocumentResponse])
async def upload_multiple_files(
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Upload multiple files at once.
    
    All files will be processed asynchronously.
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed per batch"
        )
    
    responses = []
    
    for file in files:
        try:
            # Use the single upload logic
            result = await upload_file(file, background_tasks, db)
            responses.append(result)
        except HTTPException as e:
            logger.warning(f"Failed to upload {file.filename}: {e.detail}")
            # Continue with other files
            continue
    
    if not responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files were successfully uploaded"
        )
    
    return responses
