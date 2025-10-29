# services/ai_engine_service.py
"""
AI Vision Engine service for processing video frames in batches
"""
import socketio
import asyncio
import time
import os
import threading
from typing import Optional, Dict, List
from collections import defaultdict, deque
from difflib import SequenceMatcher

from services.vision_service import VisionService
from services.tts_service import TTSService
from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


# Configuration
BATCH_SIZE = getattr(settings, 'BATCH_SIZE', 4)
DELETE_PROCESSED_FRAMES = getattr(settings, 'DELETE_PROCESSED_FRAMES', False)


class AIEngineService:
    """Service for managing AI vision processing via Socket.IO with batch processing"""
    
    def __init__(self, node_url: str):
        self.sio = socketio.Client()
        self.node_url = node_url
        self.vision_service = VisionService()
        self.tts_service = TTSService()  # Add TTS service
        
        # State management
        self.current_game_id: Optional[str] = None
        self.current_player_id: Optional[str] = None
        self.ai_active = False
        
        # Batch processing - using deque for efficient queue operations
        self.batch_size = BATCH_SIZE
        self.frame_buffers: Dict[str, deque] = defaultdict(deque)
        self.processing_flags: Dict[str, bool] = defaultdict(bool)  # Track if batch is being processed
        self.buffer_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Track previous states for change detection
        self.previous_states: Dict[str, Dict] = defaultdict(lambda: {
            "status": None,
            "observation": None,
            "analysis_result": None,
            "first_message_sent": False  # Track if first message was sent
        })
        
        # Setup socket event handlers
        self._setup_socket_events()
    
    def _setup_socket_events(self):
        """Configure Socket.IO event handlers"""
        
        @self.sio.event
        def connect():
            logger.info("✅ Connected to Node backend")
            self.ai_active = True
        
        @self.sio.on("game:started")
        def on_game_started(data):
            """Handle game start event from frontend"""
            game_id = data.get("gameId")
            player_id = data.get("playerId")
            
            logger.info(f"[GAME] Started - Game: {game_id}, Player: {player_id}")
            
            self.current_game_id = game_id
            self.current_player_id = player_id
            
            # Clear any existing frame buffer for this game
            player_key = f"{game_id}:{player_id}"
            with self.buffer_locks[player_key]:
                self.frame_buffers[player_key].clear()
                self.processing_flags[player_key] = False
                # Reset previous state for new game
                self.previous_states[player_key] = {
                    "status": None,
                    "observation": None,
                    "analysis_result": None,
                    "first_message_sent": False
                }
            
            # Acknowledge to Node backend
            self.sio.emit("start-game", {
                "gameId": game_id, 
                "playerId": player_id
            })
            logger.debug("↪️ Emitted start-game acknowledgment")
        
        @self.sio.on("frame:new")
        def on_frame_new(data):
            """Handle incoming video frame(s)"""
            game_id = data.get("gameId")
            player_id = data.get("playerId")
            
            if not game_id or not player_id:
                logger.warning("⚠️ Frame missing gameId or playerId")
                return
            
            player_key = f"{game_id}:{player_id}"
            
            # Handle both single frame and batch frames from Node
            incoming_frames = data.get("frames", [data]) if "frames" in data else [data]
            
            logger.info(f"[FRAME] Received {len(incoming_frames)} frame(s) for {player_key}")
            
            # Add frames to buffer - read and store frame data immediately
            with self.buffer_locks[player_key]:
                for frame in incoming_frames:
                    frame_path = frame.get("path")
                    if frame_path and os.path.exists(frame_path):
                        try:
                            # Read frame data immediately before it gets deleted
                            with open(frame_path, "rb") as f:
                                frame_data = f.read()
                            
                            self.frame_buffers[player_key].append({
                                "data": frame_data,  # Store actual frame data
                                "path": frame_path,  # Keep path for reference
                                "ts": frame.get("ts", int(time.time() * 1000))
                            })
                            logger.debug(f"[BUFFER] Added frame data: {frame_path}")
                        except Exception as e:
                            logger.error(f"[BUFFER] Error reading frame {frame_path}: {e}")
                    else:
                        logger.warning(f"⚠️ Invalid or missing frame: {frame_path}")
                
                buffer_size = len(self.frame_buffers[player_key])
                is_processing = self.processing_flags[player_key]
                
                logger.info(f"[BUFFER] {player_key}: {buffer_size} frames (processing: {is_processing})")
                
                # Process batch if we have enough frames AND not already processing
                if buffer_size >= self.batch_size and not is_processing:
                    # Mark as processing to prevent concurrent batch processing
                    self.processing_flags[player_key] = True
                    
                    # Extract batch for processing (first 4 frames)
                    batch = []
                    for _ in range(self.batch_size):
                        if self.frame_buffers[player_key]:
                            batch.append(self.frame_buffers[player_key].popleft())
                    
                    remaining = len(self.frame_buffers[player_key])
                    logger.info(f"[BATCH] Extracted {len(batch)} frames for processing, {remaining} remaining in buffer")
                    
                    # Process batch in background thread
                    thread = threading.Thread(
                        target=self._process_batch_sync,
                        args=(batch, game_id, player_id, player_key),
                        daemon=True
                    )
                    thread.start()
                else:
                    if is_processing:
                        logger.debug(f"[BUFFER] Batch already processing, keeping {buffer_size} frames in buffer")
                    else:
                        logger.debug(f"[BUFFER] Waiting for more frames ({buffer_size}/{self.batch_size})")
        
        @self.sio.on("ai:response")
        def on_ai_response(data):
            logger.debug(f"[AI] Response acknowledged")
        
        @self.sio.on("game:ended")
        def on_game_ended(data):
            """Handle game end event"""
            game_id = data.get("gameId")
            player_id = data.get("playerId")
            player_key = f"{game_id}:{player_id}"
            
            logger.info(f"[GAME] Ended - {player_key}")
            
            # Clear frame buffer for this player
            with self.buffer_locks[player_key]:
                remaining = len(self.frame_buffers[player_key])
                if remaining > 0:
                    logger.info(f"[CLEANUP] Clearing {remaining} unprocessed frames")
                self.frame_buffers[player_key].clear()
                self.processing_flags[player_key] = False
                # Clear previous state
                self.previous_states[player_key] = {
                    "status": None,
                    "observation": None,
                    "analysis_result": None,
                    "first_message_sent": False
                }
        
        @self.sio.event
        def disconnect():
            logger.warning("❌ Disconnected from Node backend")
            self.ai_active = False
            # Clear all buffers on disconnect
            for player_key in list(self.frame_buffers.keys()):
                with self.buffer_locks[player_key]:
                    self.frame_buffers[player_key].clear()
                    self.processing_flags[player_key] = False
    
    def _should_send_update(
        self, 
        player_key: str, 
        current_analysis: Dict,
        previous_state: Dict
    ) -> bool:
        """
        Determine if we should send an update based on changes
        
        Args:
            player_key: Player identifier
            current_analysis: Current analysis data
            previous_state: Previous state data
            
        Returns:
            True if update should be sent, False otherwise
        """
        current_status = current_analysis.get("status", "ok")
        current_message = current_analysis.get("message", "")
        
        # Always send first message (baseline)
        if not previous_state["first_message_sent"]:
            logger.info(f"[CHANGE] 🆕 First analysis - sending baseline update")
            self.previous_states[player_key] = {
                "status": current_status,
                "observation": current_message,
                "analysis_result": current_message,
                "first_message_sent": True
            }
            return True
        
        # Always send if there's danger
        if current_status == "danger":
            logger.info(f"[CHANGE] 🚨 Danger detected - sending update")
            self.previous_states[player_key]["status"] = current_status
            self.previous_states[player_key]["observation"] = current_message
            self.previous_states[player_key]["analysis_result"] = current_message
            return True
        
        # Always send if status changed from ok to needs_adjustment
        if current_status == "needs_adjustment" and previous_state["status"] != "needs_adjustment":
            logger.info(f"[CHANGE] ⚠️ Adjustment needed - sending update")
            self.previous_states[player_key]["status"] = current_status
            self.previous_states[player_key]["observation"] = current_message
            self.previous_states[player_key]["analysis_result"] = current_message
            return True
        
        # Send if status changed from needs_adjustment back to ok
        if current_status == "ok" and previous_state["status"] == "needs_adjustment":
            logger.info(f"[CHANGE] ✅ Status improved to OK - sending update")
            self.previous_states[player_key]["status"] = current_status
            self.previous_states[player_key]["observation"] = current_message
            self.previous_states[player_key]["analysis_result"] = current_message
            return True
        
        # For ongoing "ok" or "needs_adjustment" status, check for significant message change
        if previous_state["analysis_result"]:
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(
                None, 
                previous_state["analysis_result"].lower(), 
                current_message.lower()
            ).ratio()
            
            # If messages are less than 70% similar, it's a new suggestion/correction
            if similarity < 0.7:
                logger.info(f"[CHANGE] 📝 New suggestion detected (similarity: {similarity:.2f}) - sending update")
                self.previous_states[player_key]["status"] = current_status
                self.previous_states[player_key]["observation"] = current_message
                self.previous_states[player_key]["analysis_result"] = current_message
                return True
            else:
                logger.debug(f"[CHANGE] No new suggestions (status: {current_status}, similarity: {similarity:.2f})")
        
        # No significant change - don't send
        logger.debug(f"[CHANGE] Maintaining current state, no update needed")
        return False
    
    def _process_batch_sync(
        self, 
        batch: List[Dict], 
        game_id: str, 
        player_id: str,
        player_key: str
    ):
        """
        Process a batch of video frames
        
        Args:
            batch: List of frame dictionaries with 'data', 'path' and 'ts'
            game_id: Game session ID
            player_id: Player ID
            player_key: Combined key for player identification
        """
        try:
            frame_paths = [frame["path"] for frame in batch]
            frame_timestamps = [frame["ts"] for frame in batch]
            
            logger.info(f"[AI] 🔄 Processing batch of {len(batch)} frames for {player_key}")
            logger.debug(f"[AI] Frame paths: {frame_paths}")
            
            # Use stored frame data instead of reading from disk
            frame_bytes_list = []
            valid_paths = []
            
            for frame in batch:
                try:
                    frame_data = frame.get("data")
                    if frame_data:
                        frame_bytes_list.append(frame_data)
                        valid_paths.append(frame["path"])
                    else:
                        logger.warning(f"⚠️ No frame data found for: {frame['path']}")
                except Exception as e:
                    logger.error(f"❌ Error accessing frame data: {e}")
            
            if not frame_bytes_list:
                logger.warning("[AI] ⚠️ No valid frames to process in batch")
                # Reset processing flag
                with self.buffer_locks[player_key]:
                    self.processing_flags[player_key] = False
                return
            
            logger.info(f"[AI] 🔍 Analyzing {len(frame_bytes_list)} valid frames...")
            
            # Analyze batch using vision service - returns detailed analysis
            analysis_data = self.vision_service.analyze_frame_batch_detailed(
                frame_bytes_list, 
                settings.VISION_TASK
            )
            
            # Check if we need to send update based on changes
            previous_state = self.previous_states[player_key]
            should_send_update = self._should_send_update(
                player_key,
                analysis_data,
                previous_state
            )
            
            if not should_send_update:
                logger.info(f"[AI] ⏭️ No significant changes detected, skipping response")
                # Reset processing flag and continue
                with self.buffer_locks[player_key]:
                    self.processing_flags[player_key] = False
                    buffer_size = len(self.frame_buffers[player_key])
                    
                    # Check for next batch
                    if buffer_size >= self.batch_size:
                        logger.info(f"[BATCH] 🔄 New batch ready! Triggering next processing cycle")
                        self.processing_flags[player_key] = True
                        
                        next_batch = []
                        for _ in range(self.batch_size):
                            if self.frame_buffers[player_key]:
                                next_batch.append(self.frame_buffers[player_key].popleft())
                        
                        remaining = len(self.frame_buffers[player_key])
                        logger.info(f"[BATCH] Extracted {len(next_batch)} frames for next batch, {remaining} remaining")
                        
                        thread = threading.Thread(
                            target=self._process_batch_sync,
                            args=(next_batch, game_id, player_id, player_key),
                            daemon=True
                        )
                        thread.start()
                return
            
            # Extract analysis result text
            analysis_result = analysis_data.get("message", "Monitoring workspace")
            
            logger.info(f"[AI] 📢 Significant change detected, sending update")
            
            # Convert analysis result to base64 audio
            logger.info(f"[TTS] Converting analysis to audio: '{analysis_result}'")
            audio_base64 = self.tts_service.generate_audio(analysis_result)
            
            if not audio_base64:
                logger.warning("[TTS] Failed to generate audio, sending without audio")
                audio_base64 = ""
            
            # Prepare response
            ai_response = {
                "gameId": game_id,
                "playerId": player_id,
                "result": analysis_result,
                "result_audio": audio_base64,  # Base64 encoded audio
                # "framePaths": valid_paths,
                # "frameCount": len(valid_paths),
                # "processed_at": int(time.time() * 1000),
                # "model_used": settings.GEMINI_MODEL,
                # "batch_processed": True,
                # "timestamps": frame_timestamps[:len(valid_paths)]
            }
            
            # Send response back to Node
            self.sio.emit("ai:response", ai_response)
            logger.info(f"[AI] ✅ Batch response sent for {len(valid_paths)} frames with audio")
            
            # Optional: Delete processed frames to save disk space
            if DELETE_PROCESSED_FRAMES:
                for frame_path in valid_paths:
                    try:
                        if os.path.exists(frame_path):
                            os.remove(frame_path)
                            logger.debug(f"[CLEANUP] 🗑️ Deleted processed frame: {frame_path}")
                    except Exception as e:
                        logger.warning(f"[CLEANUP] Could not delete {frame_path}: {e}")
            
            # Mark processing as complete and check if we need to process next batch
            with self.buffer_locks[player_key]:
                self.processing_flags[player_key] = False
                buffer_size = len(self.frame_buffers[player_key])
                
                logger.info(f"[AI] ✔️ Batch processing complete. Buffer now has {buffer_size} frames")
                
                # If we accumulated enough frames during processing, trigger next batch
                if buffer_size >= self.batch_size:
                    logger.info(f"[BATCH] 🔄 New batch ready! Triggering next processing cycle")
                    self.processing_flags[player_key] = True
                    
                    # Extract next batch
                    next_batch = []
                    for _ in range(self.batch_size):
                        if self.frame_buffers[player_key]:
                            next_batch.append(self.frame_buffers[player_key].popleft())
                    
                    remaining = len(self.frame_buffers[player_key])
                    logger.info(f"[BATCH] Extracted {len(next_batch)} frames for next batch, {remaining} remaining")
                    
                    # Process next batch in new thread
                    thread = threading.Thread(
                        target=self._process_batch_sync,
                        args=(next_batch, game_id, player_id, player_key),
                        daemon=True
                    )
                    thread.start()
            
        except Exception as e:
            logger.error(f"[AI] ❌ Batch processing error: {e}", exc_info=True)
            # Reset processing flag on error
            with self.buffer_locks[player_key]:
                self.processing_flags[player_key] = False
    
    def connect(self) -> bool:
        """
        Connect to Node backend via Socket.IO
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"🌐 Connecting to {self.node_url}...")
            self.sio.connect(
                self.node_url, 
                transports=settings.SOCKET_TRANSPORTS
            )
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
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
    
    def get_buffer_status(self) -> Dict[str, Dict]:
        """Get current buffer sizes and processing status for all players"""
        status = {}
        for player_key in list(self.frame_buffers.keys()):
            with self.buffer_locks[player_key]:
                status[player_key] = {
                    "frames_in_buffer": len(self.frame_buffers[player_key]),
                    "is_processing": self.processing_flags[player_key]
                }
        return status