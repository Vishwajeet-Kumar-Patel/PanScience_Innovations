"""
Media streaming API with HTTP range request support for video/audio playback.
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Request, Depends, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.auth import User, decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["Media"])

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"


@router.get("/{file_path:path}")
async def stream_media(
    file_path: str, 
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Stream media file with HTTP range request support for seeking.
    
    Authentication can be provided via:
    1. Authorization header (for API calls)
    2. Query parameter 'token' (for video/audio player)
    
    Users can only stream their own uploaded files.
    """
    logger.info(f"Media request: {file_path}")
    logger.info(f"Token from query: {'present' if token else 'absent'}")
    logger.info(f"Authorization header: {'present' if request.headers.get('authorization') else 'absent'}")
    
    try:
        # Try to get user from Authorization header first
        auth_header = request.headers.get("authorization")
        current_user = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token_from_header = auth_header.replace("Bearer ", "")
            try:
                token_data = decode_access_token(token_from_header)
                if token_data:
                    user_id = token_data.user_id
                    user = await db.users.find_one({"_id": user_id})
                    if user:
                        current_user = User(
                            id=str(user["_id"]),
                            email=user["email"],
                            full_name=user["full_name"],
                            is_active=user.get("is_active", True)
                        )
            except Exception as e:
                logger.warning(f"Failed to decode token from header: {e}")
        
        # If no header token, try query parameter
        if not current_user and token:
            try:
                token_data = decode_access_token(token)
                if token_data:
                    user_id = token_data.user_id
                    user = await db.users.find_one({"_id": user_id})
                    if user:
                        current_user = User(
                            id=str(user["_id"]),
                            email=user["email"],
                            full_name=user["full_name"],
                            is_active=user.get("is_active", True)
                        )
            except Exception as e:
                logger.warning(f"Failed to decode query token: {e}")
        
        # If still no user, return 401
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access media files"
            )
        
        # Look for document by file_path (which stores relative path like "video/20260130_114414_1957b0f9.mp4")
        # The request path is like "/api/v1/media/video/20260130_114414_1957b0f9.mp4"
        logger.info(f"Looking for document with file_path: {file_path}")
        
        # First, let's see what documents exist for this user
        user_docs = await db.documents.find({"user_id": current_user.id}).to_list(length=10)
        logger.info(f"User has {len(user_docs)} documents")
        for udoc in user_docs:
            logger.info(f"  Doc: file_path='{udoc.get('file_path')}', file_name='{udoc.get('metadata', {}).get('file_name')}'")
        
        # Try with forward slashes first
        doc = await db.documents.find_one({"file_path": file_path})
        
        # If not found, try with backslashes (Windows compatibility)
        if not doc:
            file_path_backslash = file_path.replace("/", "\\")
            doc = await db.documents.find_one({"file_path": file_path_backslash})
            if doc:
                logger.info(f"Found document using backslash path: {file_path_backslash}")
        
        if not doc:
            # Try with alternative format - check if uploaded file matches
            logger.warning(f"Document not found by file_path: {file_path}")
            # Search by file name instead
            file_name = file_path.split('/')[-1]
            doc = await db.documents.find_one({"metadata.file_name": file_name})
            
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Media file not found in database"
                )
        
        # Verify ownership
        if doc.get("user_id") != current_user.id:
            logger.warning(f"User {current_user.id} attempted to access file owned by {doc.get('user_id')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this media file"
            )
        
        logger.info(f"User {current_user.email} streaming: {file_path}")
        
        # Construct full file path
        full_path = UPLOAD_DIR / file_path
        
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media file not found"
            )
        
        # Get file size
        file_size = full_path.stat().st_size
        
        # Parse range header
        range_header = request.headers.get("range")
        
        if range_header:
            # Parse range like "bytes=0-1023"
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
            
            # Ensure valid range
            start = max(0, start)
            end = min(file_size - 1, end)
            content_length = end - start + 1
            
            # Open file and seek to start position
            def iter_file():
                with open(full_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    chunk_size = 8192
                    
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            # Determine content type
            content_type = "video/mp4"
            if file_path.endswith(".mp3"):
                content_type = "audio/mpeg"
            elif file_path.endswith(".wav"):
                content_type = "audio/wav"
            
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Content-Type": content_type,
            }
            
            return StreamingResponse(
                iter_file(),
                status_code=206,  # Partial Content
                headers=headers
            )
        else:
            # No range header, send entire file
            def iter_full_file():
                with open(full_path, "rb") as f:
                    chunk_size = 8192
                    while chunk := f.read(chunk_size):
                        yield chunk
            
            # Determine content type
            content_type = "video/mp4"
            if file_path.endswith(".mp3"):
                content_type = "audio/mpeg"
            elif file_path.endswith(".wav"):
                content_type = "audio/wav"
            
            headers = {
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": content_type,
            }
            
            return StreamingResponse(
                iter_full_file(),
                headers=headers
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream media: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stream media file"
        )
