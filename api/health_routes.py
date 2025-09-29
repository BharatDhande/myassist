# api/health_routes.py
"""
Health check and status routes
"""
from fastapi import APIRouter
from datetime import datetime
from core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "voice_commands": "operational",
            "ai_vision": "operational" if settings.ENABLE_AI_VISION else "disabled"
        }
    }


@router.get("/status")
async def get_status():
    """Detailed status endpoint"""
    return {
        "service": "AR/VR Assistant System",
        "version": "2.0.0",
        "uptime": "running",
        "configuration": {
            "ai_vision_enabled": settings.ENABLE_AI_VISION,
            "node_backend": settings.NODE_BACKEND_URL,
            "gemini_model": settings.GEMINI_MODEL,
            "fuzzy_threshold": settings.FUZZY_THRESHOLD
        }
    }