# core/config.py
"""
Centralized configuration management using environment variables
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 4443
    DEBUG: bool = False
    
    # AI Vision Configuration
    ENABLE_AI_VISION: bool = True
    NODE_BACKEND_URL: str = os.getenv(
        "NODE_BACKEND_URL"
    )
    GEMINI_API_KEY: str = os.getenv(
        "GEMINI_API_KEY"
    )
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    VISION_TASK: str = "assisting worker working at a plant"
    
    # Voice Command Configuration
    FUZZY_THRESHOLD: int = 75
    TTS_LANGUAGE: str = "en"
    TTS_SPEED: float = 1.0
    
    # Processing Configuration
    MAX_FRAME_WORKERS: int = 3
    FRAME_TIMEOUT: int = 10
    IMAGE_MAX_SIZE: int = 1024
    
    # Socket Configuration
    SOCKET_TRANSPORTS: list = ["websocket", "polling"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()