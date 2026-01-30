"""
Unified transcription service supporting multiple providers:
- Local Whisper (free, runs locally)
- OpenAI Whisper API (paid, best quality)
- Deepgram (paid, fastest)
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import tempfile
import os

from app.core.config import settings
from app.models import Timestamp

logger = logging.getLogger(__name__)


class UnifiedTranscriptionService:
    """
    Unified service for transcribing audio/video files using different providers.
    
    Providers:
    - local: Uses local Whisper model (free, ~75-465MB download, slower)
    - openai: Uses OpenAI Whisper API (paid, best quality, 25MB limit per file)
    - deepgram: Uses Deepgram API (paid, fastest, good quality)
    """
    
    def __init__(self, provider: Optional[str] = None):
        """
        Initialize transcription service.
        
        Args:
            provider: Transcription provider ('local', 'openai', 'deepgram')
                     If None, uses TRANSCRIPTION_PROVIDER from settings
        """
        self.provider = provider or settings.TRANSCRIPTION_PROVIDER
        self._service = None
        
        logger.info(f"Initializing transcription service with provider: {self.provider}")
        
        # Initialize the appropriate service
        if self.provider == "local":
            from app.services.free_transcription import FreeTranscriptionService
            self._service = FreeTranscriptionService(
                model_size=settings.WHISPER_MODEL_SIZE
            )
        elif self.provider == "openai":
            from app.services.transcription import TranscriptionService
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
            self._service = TranscriptionService()
        elif self.provider == "deepgram":
            if not settings.DEEPGRAM_API_KEY:
                raise ValueError("DEEPGRAM_API_KEY is required for Deepgram provider")
            self._service = DeepgramTranscriptionService()
        else:
            raise ValueError(f"Unknown transcription provider: {self.provider}")
    
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
            logger.info(f"Transcribing with {self.provider}: {file_path}")
            return await self._service.transcribe(file_path, language)
        except Exception as e:
            logger.error(f"Transcription failed with {self.provider}: {e}")
            raise
    
    async def extract_audio_from_video(self, video_path: Path) -> Path:
        """Extract audio track from video file."""
        try:
            from moviepy.editor import VideoFileClip
            
            # Create temp audio file
            audio_path = video_path.with_suffix('.mp3')
            
            with VideoFileClip(str(video_path)) as video:
                if video.audio is None:
                    raise ValueError("Video file has no audio track")
                
                video.audio.write_audiofile(
                    str(audio_path),
                    logger=None  # Suppress moviepy logs
                )
            
            logger.info(f"Audio extracted from video: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Failed to extract audio from video: {e}")
            raise


class DeepgramTranscriptionService:
    """Service for transcribing audio/video using Deepgram API."""
    
    def __init__(self):
        """Initialize Deepgram client."""
        from deepgram import DeepgramClient, PrerecordedOptions
        
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY)
        self.PrerecordedOptions = PrerecordedOptions
        logger.info("Deepgram client initialized")
    
    async def transcribe(
        self,
        file_path: Path,
        language: Optional[str] = None
    ) -> Tuple[str, List[Timestamp], Dict]:
        """
        Transcribe audio/video file using Deepgram.
        
        Args:
            file_path: Path to audio/video file
            language: Optional language code (e.g., 'en', 'es')
            
        Returns:
            Tuple of (full_transcription, timestamps, metadata)
        """
        try:
            logger.info(f"Transcribing with Deepgram: {file_path}")
            
            # Read audio file
            with open(file_path, 'rb') as audio_file:
                buffer_data = audio_file.read()
            
            # Configure options
            options = self.PrerecordedOptions(
                model="nova-2",  # Latest model
                smart_format=True,
                punctuate=True,
                paragraphs=True,
                utterances=True,
                language=language or "en",
            )
            
            # Transcribe using prerecorded method
            payload = {"buffer": buffer_data}
            response = self.client.listen.prerecorded.v("1").transcribe_file(
                payload,
                options
            )
            
            # Extract transcription
            if not response.results or not response.results.channels:
                raise ValueError("No transcription results from Deepgram")
            
            channel = response.results.channels[0]
            
            # Get full text
            transcription_text = channel.alternatives[0].transcript
            
            # Extract timestamps from paragraphs or words
            timestamps = []
            
            # Try to use paragraphs first
            if hasattr(channel.alternatives[0], 'paragraphs') and channel.alternatives[0].paragraphs:
                paragraphs_list = channel.alternatives[0].paragraphs.paragraphs if hasattr(channel.alternatives[0].paragraphs, 'paragraphs') else []
                for paragraph in paragraphs_list:
                    # Deepgram paragraphs have 'sentences' array, not 'text' directly
                    para_text = ""
                    if hasattr(paragraph, 'sentences'):
                        para_text = ' '.join([s.text for s in paragraph.sentences if hasattr(s, 'text')])
                    elif hasattr(paragraph, 'text'):
                        para_text = paragraph.text
                    
                    if para_text:
                        timestamps.append(Timestamp(
                            start=paragraph.start if hasattr(paragraph, 'start') else 0,
                            end=paragraph.end if hasattr(paragraph, 'end') else 0,
                            text=para_text.strip()
                        ))
            
            # Fallback to words if no paragraphs
            if not timestamps and hasattr(channel.alternatives[0], 'words') and channel.alternatives[0].words:
                # Group words into sentences (approximate)
                sentence_words = []
                sentence_start = None
                
                for word in channel.alternatives[0].words:
                    if sentence_start is None:
                        sentence_start = word.start
                    
                    sentence_words.append(word.word)
                    
                    # End sentence on punctuation or every 20 words
                    if (word.word.endswith(('.', '!', '?')) or 
                        len(sentence_words) >= 20):
                        timestamps.append(Timestamp(
                            start=sentence_start,
                            end=word.end,
                            text=' '.join(sentence_words)
                        ))
                        sentence_words = []
                        sentence_start = None
                
                # Add remaining words
                if sentence_words:
                    last_word = channel.alternatives[0].words[-1]
                    timestamps.append(Timestamp(
                        start=sentence_start or last_word.start,
                        end=last_word.end,
                        text=' '.join(sentence_words)
                    ))
            
            # Metadata
            metadata = {
                "provider": "deepgram",
                "model": "nova-2",
                "language": language or "en",
                "duration": response.metadata.duration if hasattr(response, 'metadata') else 0,
                "segments": len(timestamps),
                "confidence": channel.alternatives[0].confidence if hasattr(channel.alternatives[0], 'confidence') else None
            }
            
            logger.info(
                f"Deepgram transcription complete: {len(transcription_text)} chars, "
                f"{len(timestamps)} segments"
            )
            
            return transcription_text, timestamps, metadata
            
        except Exception as e:
            logger.error(f"Deepgram transcription failed: {e}")
            raise


# Factory function to get the appropriate service
def get_transcription_service(provider: Optional[str] = None) -> UnifiedTranscriptionService:
    """
    Get transcription service instance.
    
    Args:
        provider: Optional provider override ('local', 'openai', 'deepgram')
    
    Returns:
        UnifiedTranscriptionService instance
    """
    return UnifiedTranscriptionService(provider=provider)


# Singleton for default provider
_default_service = None


def get_default_transcription_service() -> UnifiedTranscriptionService:
    """Get or create singleton transcription service with default provider."""
    global _default_service
    if _default_service is None:
        _default_service = UnifiedTranscriptionService()
    return _default_service
