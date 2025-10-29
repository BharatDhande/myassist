# services/ai_engine_service.py
"""
AI Vision Engine service for processing video frames
"""
import socketio
import asyncio
import time
import os
import threading
from typing import Optional

from services.vision_service import VisionService
from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


class AIEngineService:
    """Service for managing AI vision processing via Socket.IO"""
    
    def __init__(self, node_url: str):
        # Normalize URL (remove trailing slash)
        self.node_url = node_url.rstrip('/')
        
        # Configure Socket.IO client with better error handling
        self.sio = socketio.Client(
            logger=False,  # Disable socket.io internal logging
            engineio_logger=False,
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            reconnection_delay_max=5,
        )
        
        self.vision_service = VisionService()
        
        # State management
        self.current_game_id: Optional[str] = None
        self.current_player_id: Optional[str] = None
        self.frame_cache = set()
        self.ai_active = False
        
        # Setup socket event handlers
        self._setup_socket_events()
    
    def _setup_socket_events(self):
        """Configure Socket.IO event handlers"""
        
        @self.sio.event
        def connect():
            logger.info("✅ Connected to Node backend")
            self.ai_active = True
        
        @self.sio.event
        def connect_error(data):
            logger.error(f"❌ Connection error: {data}")
        
        @self.sio.on("game:started")
        def on_game_started(data):
            """Handle game start event from frontend"""
            game_id = data.get("gameId")
            player_id = data.get("playerId")
            
            logger.info(f"[GAME] Started - Game: {game_id}, Player: {player_id}")
            
            self.current_game_id = game_id
            self.current_player_id = player_id
            
            # Acknowledge to Node backend
            self.sio.emit("start-game", {
                "gameId": game_id, 
                "playerId": player_id
            })
            logger.debug("↪️ Emitted start-game acknowledgment")
        
        @self.sio.on("frame:new")
        def on_frame_new(frame):
            """Handle incoming video frame"""
            game_id = frame.get("gameId")
            player_id = frame.get("playerId")
            frame_path = frame.get("path")
            
            if not frame_path:
                logger.warning("⚠️ Frame missing 'path' field")
                return
            
            # Deduplicate frames
            if frame_path in self.frame_cache:
                logger.debug(f"[FRAME] Skipping duplicate: {frame_path}")
                return
            
            self.frame_cache.add(frame_path)
            logger.info(f"[FRAME] Received: {frame_path}")
            
            # Process frame in background thread
            thread = threading.Thread(
                target=self._process_frame_sync,
                args=(frame_path, game_id, player_id),
                daemon=True
            )
            thread.start()
        
        @self.sio.on("ai:response")
        def on_ai_response(data):
            logger.debug(f"[AI] Response acknowledged: {data.get('framePath')}")
        
        @self.sio.event
        def disconnect():
            logger.warning("❌ Disconnected from Node backend")
            self.ai_active = False
    
    def _process_frame_sync(
        self, 
        frame_path: str, 
        game_id: str, 
        player_id: str
    ):
        """
        Process a single video frame
        
        Args:
            frame_path: Path to the frame image file
            game_id: Game session ID
            player_id: Player ID
        """
        try:
            # Validate frame exists
            if not os.path.exists(frame_path):
                logger.error(f"❌ Frame not found: {frame_path}")
                return
            
            # Read frame data
            with open(frame_path, "rb") as f:
                frame_bytes = f.read()
            
            logger.info(f"[AI] Processing frame: {frame_path}")
            
            # Analyze frame using vision service
            analysis_result = self.vision_service.analyze_frame_batch(
                [frame_bytes], 
                settings.VISION_TASK
            )
            
            # Prepare response
            ai_response = {
                "gameId": game_id,
                "playerId": player_id,
                "framePath": frame_path,
                "result": analysis_result,
                "processed_at": int(time.time() * 1000),
                "model_used": settings.GEMINI_MODEL,
                "batch_processed": False,
            }
            
            # Send response back to Node
            self.sio.emit("ai:response", ai_response)
            logger.info(f"[AI] Response sent for: {frame_path}")
            
        except Exception as e:
            logger.error(f"[AI] Frame processing error: {e}", exc_info=True)
    
    def connect(self) -> bool:
        """
        Connect to Node backend via Socket.IO with enhanced error handling
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"🌐 Connecting to {self.node_url}...")
            
            # Attempt Socket.IO connection directly
            self.sio.connect(
                self.node_url,
                transports=settings.SOCKET_TRANSPORTS,
                wait_timeout=10,  # Increased timeout
                namespaces=['/']  # Explicitly specify namespace
            )
            
            # Wait a moment to ensure connection is established
            time.sleep(1)
            
            if self.sio.connected:
                logger.info("✅ Socket.IO connection established")
                return True
            else:
                logger.error("❌ Socket.IO failed to connect")
                return False
                
        except socketio.exceptions.ConnectionError as e:
            logger.error(f"❌ Socket.IO Connection Error: {e}")
            logger.info("Possible causes:")
            logger.info("  1. Backend server not running")
            logger.info("  2. CORS configuration blocking connection")
            logger.info("  3. Incorrect Socket.IO namespace or path")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected connection error: {e}", exc_info=True)
            return False
    
    def disconnect(self):
        """Disconnect from Node backend"""
        if self.sio.connected:
            self.sio.disconnect()
            logger.info("🔌 Disconnected from Node backend")
    
    async def run(self):
        """Run the AI engine service (keeps it alive)"""
        try:
            logger.info("🚀 AI Engine service running...")
            while self.ai_active:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[AI] Service error: {e}")
        finally:
            self.disconnect()