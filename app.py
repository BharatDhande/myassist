# assistant_server.py
from fuzzywuzzy import process
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from commands import COMMANDS, get_canonical_command
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from utils import * 
import uvicorn 
import pydantic 
import typing
import base64
from io import BytesIO
from gtts import gTTS

# ===========================
# CONFIGURATION
# ===========================
FUZZY_THRESHOLD = 75
TTS_LANGUAGE = 'en'
TTS_SPEED = 1.0  # Normal speed

command_list = list(COMMANDS.keys())

# ===========================
# FASTAPI APP SETUP
# ===========================
app = FastAPI(
    title="Voice Assistant Server",
    description="WebSocket server that receives voice text, matches commands, and forwards to AR/VR API",
    version="1.0.0"
)

def generate_speech_audio(text: str, lang: str = TTS_LANGUAGE, speed: float = TTS_SPEED) -> str:
    """Generate audio from text and return as base64 encoded MP3 string"""
    try:
        # Create gTTS object
        tts = gTTS(text=text, lang=lang, slow=False, lang_check=False)
        
        # Create a BytesIO buffer to store the audio
        audio_buffer = BytesIO()
        
        # Save audio to buffer (MP3 format by default)
        tts.write_to_fp(audio_buffer)
        
        # Get the audio data and encode to base64
        audio_buffer.seek(0)
        audio_data = audio_buffer.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return audio_base64
    except Exception as e:
        print(f"[TTS ERROR] {e}")
        return None

@app.get("/")
async def get():
    return {"success": "Welcome to the Voice Assistant Server!"}

class VoiceCommandRequest(BaseModel):
    text: str

class VoiceCommandResponse(BaseModel):
    status: str
    suggestion: str            # 👈 natural TTS response
    speak_back: Optional[str] = None  # 👈 audio data (base64 encoded MP3)
    command_back: Optional[str] = None  # 👈 canonical command
    score: Optional[int] = None
    best_guess: Optional[str] = None

@app.post("/command", response_model=VoiceCommandResponse)
async def process_voice_command(request: VoiceCommandRequest):
    user_text = request.text.lower().strip()
    print(f"[HEARD] '{user_text}'")

    if not user_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        match, score = process.extractOne(user_text, list(COMMANDS.keys()))

        if score >= FUZZY_THRESHOLD:
            response_text = COMMANDS[match]()          # natural reply
            canonical = get_canonical_command(match)   # normalized command
            
            # Generate audio for the response
            audio_data = generate_speech_audio(response_text)
            
            return VoiceCommandResponse(
                status="success",
                suggestion=response_text,
                speak_back=audio_data,
                command_back=canonical,
                score=score
            )
        else:
            response_text = "Sorry, I didn't catch that."
            canonical = get_canonical_command(match)
            
            # Generate audio for the response
            audio_data = generate_speech_audio(response_text)
            
            return VoiceCommandResponse(
                status="no_match",
                suggestion=response_text,
                speak_back=audio_data,
                best_guess=canonical,
                score=score
            )

    except Exception as e:
        print(f"[COMMAND ERROR] {e}")
        raise HTTPException(status_code=500, detail="Command processing failed")



# ===========================
# RUN SERVER
# ===========================
if __name__ == "__main__":
    print("🚀 Assistant Server (FastAPI + WebSocket) running on http://localhost:4003")
    uvicorn.run(app, host="0.0.0.0", port=4003)