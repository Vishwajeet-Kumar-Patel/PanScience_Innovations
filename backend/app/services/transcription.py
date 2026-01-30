"""
Audio and video transcription service using OpenAI Whisper API.
Extracts transcriptions with timestamps from media files.
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import openai
from openai import AsyncOpenAI
from pydub import AudioSegment
import tempfile
import os

from app.core.config import settings
from app.models import Timestamp

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio and video files using Whisper API."""
    
    # Whisper API file size limit (25MB)
    MAX_FILE_SIZE = 25 * 1024 * 1024
    
    # Chunk duration for large files (minutes)
    CHUNK_DURATION_MS = 10 * 60 * 1000  # 10 minutes
    
    def __init__(self):
        """Initialize transcription service."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def transcribe(
        self, 
        file_path: Path,
        language: Optional[str] = None
    ) -> Tuple[str, List[Timestamp], Dict]:
        """
        Transcribe audio/video file with timestamps.
        
        Args:
            file_path: Path to audio/video file
            language: Optional language code (e.g., 'en', 'es')
            
        Returns:
            Tuple of (full_transcription, timestamps, metadata)
        """
        try:
            logger.info(f"Starting transcription for: {file_path}")
            
            # Get file size and duration
            file_size = file_path.stat().st_size
            audio_info = await self._get_audio_info(file_path)
            
            # If file is too large, split into chunks
            if file_size > self.MAX_FILE_SIZE:
                logger.info(f"File too large ({file_size} bytes), splitting into chunks")
                return await self._transcribe_large_file(file_path, language)
            
            # Transcribe directly
            transcription_text, timestamps = await self._transcribe_file(
                file_path, 
                language
            )
            
            metadata = {
                "duration": audio_info["duration"],
                "format": audio_info["format"],
                "channels": audio_info.get("channels"),
                "sample_rate": audio_info.get("sample_rate"),
            }
            
            logger.info(
                f"Transcription completed: {len(transcription_text)} characters, "
                f"{len(timestamps)} segments"
            )
            
            return transcription_text, timestamps, metadata
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def _transcribe_file(
        self,
        file_path: Path,
        language: Optional[str] = None,
        offset: float = 0.0
    ) -> Tuple[str, List[Timestamp]]:
        """Transcribe a single file using Whisper API."""
        try:
            with open(file_path, 'rb') as audio_file:
                # Use verbose_json response format to get timestamps
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    language=language
                )
            
            # Extract full text
            transcription_text = response.text
            
            # Extract timestamps from segments
            timestamps = []
            if hasattr(response, 'segments') and response.segments:
                for segment in response.segments:
                    timestamps.append(Timestamp(
                        start=segment['start'] + offset,
                        end=segment['end'] + offset,
                        text=segment['text'].strip()
                    ))
            
            return transcription_text, timestamps
            
        except Exception as e:
            logger.error(f"Whisper API call failed: {e}")
            raise
    
    async def _transcribe_large_file(
        self,
        file_path: Path,
        language: Optional[str] = None
    ) -> Tuple[str, List[Timestamp], Dict]:
        """Split large file into chunks and transcribe each."""
        try:
            # Load audio file
            audio = AudioSegment.from_file(str(file_path))
            duration_ms = len(audio)
            
            all_text = []
            all_timestamps = []
            
            # Process in chunks
            chunk_count = (duration_ms // self.CHUNK_DURATION_MS) + 1
            logger.info(f"Processing {chunk_count} chunks")
            
            for i in range(chunk_count):
                start_ms = i * self.CHUNK_DURATION_MS
                end_ms = min((i + 1) * self.CHUNK_DURATION_MS, duration_ms)
                
                # Extract chunk
                chunk = audio[start_ms:end_ms]
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(
                    suffix=".mp3",
                    delete=False
                ) as temp_file:
                    chunk.export(temp_file.name, format="mp3")
                    temp_path = Path(temp_file.name)
                
                try:
                    # Transcribe chunk
                    offset_seconds = start_ms / 1000.0
                    text, timestamps = await self._transcribe_file(
                        temp_path,
                        language,
                        offset=offset_seconds
                    )
                    
                    all_text.append(text)
                    all_timestamps.extend(timestamps)
                    
                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
                
                logger.info(f"Chunk {i+1}/{chunk_count} completed")
            
            # Combine results
            full_text = " ".join(all_text)
            
            metadata = {
                "duration": duration_ms / 1000.0,
                "format": file_path.suffix[1:],
                "chunks_processed": chunk_count,
            }
            
            return full_text, all_timestamps, metadata
            
        except Exception as e:
            logger.error(f"Large file transcription failed: {e}")
            raise
    
    async def _get_audio_info(self, file_path: Path) -> Dict:
        """Get audio file information."""
        try:
            audio = AudioSegment.from_file(str(file_path))
            
            return {
                "duration": len(audio) / 1000.0,  # Convert to seconds
                "format": file_path.suffix[1:],
                "channels": audio.channels,
                "sample_rate": audio.frame_rate,
                "sample_width": audio.sample_width,
            }
        except Exception as e:
            logger.warning(f"Failed to get audio info: {e}")
            return {
                "duration": 0,
                "format": file_path.suffix[1:],
            }
    
    async def extract_audio_from_video(self, video_path: Path) -> Path:
        """Extract audio track from video file."""
        try:
            from moviepy.editor import VideoFileClip
            
            # Create temp audio file
            audio_path = video_path.with_suffix('.mp3')
            
            with VideoFileClip(str(video_path)) as video:
                video.audio.write_audiofile(
                    str(audio_path),
                    logger=None  # Suppress moviepy logs
                )
            
            logger.info(f"Audio extracted from video: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Failed to extract audio from video: {e}")
            raise


# Singleton instance
transcription_service = TranscriptionService()
