"""
Free transcription service using local Whisper model (no API costs).
"""
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import whisper
from app.models import Timestamp

logger = logging.getLogger(__name__)


class FreeTranscriptionService:
    """Service for transcribing audio/video using local Whisper model."""
    
    def __init__(self, model_size: str = "base"):
        """
        Initialize transcription service with local Whisper.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
                       base = good balance of speed/accuracy (free, ~75MB)
                       small = better quality (~465MB)
        """
        logger.info(f"Loading Whisper {model_size} model (free, local)")
        self.model = whisper.load_model(model_size)
        logger.info("Whisper model loaded successfully")
    
    async def transcribe(
        self,
        file_path: Path,
        language: str = None
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
            logger.info(f"Transcribing: {file_path}")
            
            # Transcribe with Whisper
            result = self.model.transcribe(
                str(file_path),
                language=language,
                verbose=False,
                word_timestamps=False  # Segment-level is enough
            )
            
            # Extract text
            transcription_text = result["text"]
            
            # Extract timestamps from segments
            timestamps = []
            for segment in result.get("segments", []):
                timestamps.append(Timestamp(
                    start=segment["start"],
                    end=segment["end"],
                    text=segment["text"].strip()
                ))
            
            # Metadata
            metadata = {
                "duration": result.get("duration", 0),
                "language": result.get("language", "unknown"),
                "segments": len(timestamps)
            }
            
            logger.info(
                f"Transcription complete: {len(transcription_text)} chars, "
                f"{len(timestamps)} segments"
            )
            
            return transcription_text, timestamps, metadata
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    async def extract_audio_from_video(self, video_path: Path) -> Path:
        """Extract audio from video file (reuse from original service)."""
        from app.services.transcription import TranscriptionService
        service = TranscriptionService()
        return await service.extract_audio_from_video(video_path)


# Singleton instance
_transcription_service = None


def get_transcription_service() -> FreeTranscriptionService:
    """Get or create singleton transcription service."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = FreeTranscriptionService()
    return _transcription_service
