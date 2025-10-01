# api/health_routes.py
"""
Health check and status routes
"""
from fastapi import APIRouter, Request
from datetime import datetime
from core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    # Access AI service from app state
    ai_service = getattr(request.app.state, 'ai_service', None)
    
    buffer_status = {}
    if ai_service:
        buffer_status = ai_service.get_buffer_status()
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "voice_commands": "operational",
            "ai_vision": "operational" if settings.ENABLE_AI_VISION else "disabled"
        },
        "buffer_status": buffer_status
    }


@router.get("/status")
async def get_status(request: Request):
    """Detailed status endpoint"""
    # Access AI service from app state
    ai_service = getattr(request.app.state, 'ai_service', None)
    
    buffer_info = {}
    if ai_service:
        buffer_status = ai_service.get_buffer_status()
        buffer_info = {
            "active_players": len(buffer_status),
            "buffers": buffer_status,
            "batch_size": ai_service.batch_size
        }
    
    return {
        "service": "AR/VR Assistant System",
        "version": "2.1.0",
        "uptime": "running",
        "configuration": {
            "ai_vision_enabled": settings.ENABLE_AI_VISION,
            "node_backend": settings.NODE_BACKEND_URL,
            "gemini_model": settings.GEMINI_MODEL,
            "fuzzy_threshold": settings.FUZZY_THRESHOLD,
            "batch_size": settings.BATCH_SIZE,
            "delete_processed_frames": settings.DELETE_PROCESSED_FRAMES
        },
        "batch_processing": buffer_info
    }