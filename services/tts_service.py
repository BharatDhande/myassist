# services/tts_service.py
"""
Text-to-Speech service
"""
import base64
from io import BytesIO
from gtts import gTTS
from typing import Optional

from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


class TTSService:
    """Service for converting text to speech"""
    
    def __init__(self):
        self.language = settings.TTS_LANGUAGE
        self.speed = settings.TTS_SPEED
    
    def generate_audio(self, text: str) -> Optional[str]:
        """
        Generate audio from text and return as base64 encoded MP3
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Base64 encoded MP3 audio string or None on error
        """
        try:
            logger.debug(f"[TTS] Generating audio for: '{text}'")
            
            # Create gTTS object
            tts = gTTS(
                text=text, 
                lang=self.language, 
                slow=False, 
                lang_check=False
            )
            
            # Create BytesIO buffer for audio
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            
            # Encode to base64
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            logger.debug(f"[TTS] Audio generated successfully ({len(audio_base64)} bytes)")
            return audio_base64
            
        except Exception as e:
            logger.error(f"[TTS] Audio generation error: {e}")
            return None