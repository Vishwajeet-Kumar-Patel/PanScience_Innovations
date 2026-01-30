"""
File upload service for handling document, audio, and video uploads.
Includes validation, storage, and metadata extraction.
"""
import os
import uuid
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import logging
import magic
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.models import FileType, DocumentMetadata

logger = logging.getLogger(__name__)


class FileUploadService:
    """Service for handling file uploads with validation and storage."""
    
    # MIME type mappings
    MIME_TYPE_MAPPING = {
        "application/pdf": FileType.PDF,
        "audio/mpeg": FileType.AUDIO,
        "audio/mp3": FileType.AUDIO,
        "audio/wav": FileType.AUDIO,
        "audio/x-wav": FileType.AUDIO,
        "audio/mp4": FileType.AUDIO,
        "audio/x-m4a": FileType.AUDIO,
        "video/mp4": FileType.VIDEO,
        "video/mpeg": FileType.VIDEO,
        "video/x-msvideo": FileType.VIDEO,
        "video/quicktime": FileType.VIDEO,
    }
    
    def __init__(self):
        """Initialize upload service."""
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for each file type
        (self.upload_dir / "pdf").mkdir(exist_ok=True)
        (self.upload_dir / "audio").mkdir(exist_ok=True)
        (self.upload_dir / "video").mkdir(exist_ok=True)
    
    def _validate_file_extension(self, filename: str) -> bool:
        """Validate file extension."""
        extension = filename.split(".")[-1].lower()
        return extension in settings.ALLOWED_EXTENSIONS
    
    def _get_file_type(self, mime_type: str, filename: str) -> FileType:
        """Determine file type from MIME type."""
        # Try MIME type first
        file_type = self.MIME_TYPE_MAPPING.get(mime_type)
        
        # Fallback to extension
        if not file_type:
            extension = filename.split(".")[-1].lower()
            if extension == "pdf":
                file_type = FileType.PDF
            elif extension in ["mp3", "wav", "m4a"]:
                file_type = FileType.AUDIO
            elif extension in ["mp4", "avi", "mov"]:
                file_type = FileType.VIDEO
        
        return file_type
    
    async def validate_file(self, file: UploadFile) -> Tuple[FileType, str]:
        """
        Validate uploaded file.
        
        Returns:
            Tuple of (FileType, mime_type)
        
        Raises:
            HTTPException if validation fails
        """
        # Check filename
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        # Validate extension
        if not self._validate_file_extension(file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Read first chunk to detect MIME type
        file_header = await file.read(2048)
        await file.seek(0)  # Reset file pointer
        
        # Detect MIME type
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_buffer(file_header)
        except Exception as e:
            logger.warning(f"Failed to detect MIME type: {e}, using content_type")
            mime_type = file.content_type or "application/octet-stream"
        
        # Get file type
        file_type = self._get_file_type(mime_type, file.filename)
        
        if not file_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {mime_type}"
            )
        
        # Check file size (read in chunks to avoid memory issues)
        file_size = 0
        chunk_size = 8192
        await file.seek(0)
        
        while chunk := await file.read(chunk_size):
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size: {settings.MAX_FILE_SIZE / (1024*1024)}MB"
                )
        
        await file.seek(0)  # Reset for actual storage
        
        return file_type, mime_type
    
    def _generate_unique_filename(self, original_filename: str, file_type: FileType) -> str:
        """Generate unique filename to avoid collisions."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        extension = original_filename.split(".")[-1].lower()
        
        return f"{timestamp}_{unique_id}.{extension}"
    
    async def save_file(
        self, 
        file: UploadFile, 
        file_type: FileType
    ) -> Tuple[str, str, int]:
        """
        Save uploaded file to disk.
        
        Returns:
            Tuple of (file_id, file_path, file_size)
        """
        # Generate unique filename
        unique_filename = self._generate_unique_filename(file.filename, file_type)
        file_id = unique_filename.split(".")[0]
        
        # Determine subdirectory based on file type
        subdir = file_type.value
        file_path = self.upload_dir / subdir / unique_filename
        
        # Save file
        file_size = 0
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                while chunk := await file.read(8192):
                    file_size += len(chunk)
                    await f.write(chunk)
            
            logger.info(f"File saved successfully: {file_path} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            # Clean up partial file
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save file"
            )
        
        # Return relative path from upload_dir
        # Convert to forward slashes for URL compatibility (works on both Windows and Unix)
        relative_path = str(file_path.relative_to(self.upload_dir)).replace("\\", "/")
        return file_id, relative_path, file_size
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage."""
        try:
            full_path = self.upload_dir / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"File deleted: {file_path}")
                return True
            else:
                logger.warning(f"File not found for deletion: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_file_path(self, relative_path: str) -> Path:
        """Get absolute file path."""
        return self.upload_dir / relative_path
    
    async def create_metadata(
        self,
        filename: str,
        file_type: FileType,
        file_size: int,
        mime_type: str
    ) -> DocumentMetadata:
        """Create document metadata."""
        metadata = DocumentMetadata(
            file_name=filename,
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type
        )
        
        return metadata


# Singleton instance
file_upload_service = FileUploadService()
