# main.py
"""
Unified AR/VR Assistant System
Combines voice command processing and AI vision analysis
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.voice_routes import router as voice_router
from api.health_routes import router as health_router
from services.ai_engine_service import AIEngineService
from core.config import settings
from core.logging_config import setup_logging

# Setup logging
logger = setup_logging()

# Global AI Engine Service instance
ai_service: AIEngineService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global ai_service
    
    # Startup
    logger.info("🚀 Starting AR/VR Assistant System...")
    
    # Initialize AI Engine Service
    if settings.ENABLE_AI_VISION:
        ai_service = AIEngineService(settings.NODE_BACKEND_URL)
        if ai_service.connect():
            logger.info("✅ AI Vision Engine connected")
            # Start AI engine in background
            asyncio.create_task(ai_service.run())
        else:
            logger.warning("⚠️ AI Vision Engine failed to connect")
    else:
        logger.info("ℹ️ AI Vision Engine disabled in config")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down AR/VR Assistant System...")
    if ai_service:
        ai_service.disconnect()
    logger.info("👋 Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AR/VR Assistant System",
    description="Unified system for voice commands and AI vision analysis",
    version="2.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(voice_router, prefix="/api", tags=["Voice Commands"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AR/VR Assistant System",
        "version": "2.0.0",
        "status": "running",
        "features": {
            "voice_commands": True,
            "ai_vision": settings.ENABLE_AI_VISION
        }
    }


def main():
    """Main entry point"""
    logger.info(f"🌐 Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()