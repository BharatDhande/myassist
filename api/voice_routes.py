# api/voice_routes.py
"""
Voice command API routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.voice_command_service import VoiceCommandService
from services.tts_service import TTSService
from core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize services
voice_service = VoiceCommandService()
tts_service = TTSService()


class VoiceCommandRequest(BaseModel):
    """Voice command request model"""
    text: str


class VoiceCommandResponse(BaseModel):
    """Voice command response model"""
    status: str
    suggestion: str
    speak_back: Optional[str] = None
    command_back: Optional[str] = None
    score: Optional[int] = None
    best_guess: Optional[str] = None


@router.post("/command", response_model=VoiceCommandResponse)
async def process_voice_command(request: VoiceCommandRequest):
    """
    Process voice command and return response with TTS audio
    """
    try:
        user_text = request.text.lower().strip()
        logger.info(f"[VOICE] Received command: '{user_text}'")

        if not user_text:
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Process command
        result = voice_service.process_command(user_text)
        
        # Generate TTS audio
        if result["status"] == "success":
            audio_data = tts_service.generate_audio(result["suggestion"])
            
            return VoiceCommandResponse(
                status="success",
                suggestion=result["suggestion"],
                speak_back=audio_data,
                command_back=result["canonical"],
                score=result["score"]
            )
        else:
            audio_data = tts_service.generate_audio(result["suggestion"])
            
            return VoiceCommandResponse(
                status="no_match",
                suggestion=result["suggestion"],
                speak_back=audio_data,
                best_guess=result["best_guess"],
                score=result["score"]
            )

    except Exception as e:
        logger.error(f"[VOICE] Command processing error: {e}")
        raise HTTPException(status_code=500, detail="Command processing failed")