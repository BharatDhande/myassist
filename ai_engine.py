# ai_engine.py
import socketio
import asyncio
import time
import os
from typing import List
from vision import analyze_frame_batch, TASK

class HybridAIBackend:
    def __init__(self, node_url: str):
        self.sio = socketio.Client()
        self.node_url = node_url
        self.current_game_id = None
        self.current_player_id = None
        self.frame_cache = set()
        self.ai_active = False

        self.setup_socket_events()

    def setup_socket_events(self):
        @self.sio.event
        def connect():
            print("✅ Connected to Node backend")
            self.ai_active = True

        @self.sio.on("game:started")
        def on_game_started(data):
            """Frontend triggers this when a new game starts"""
            game_id = data.get("gameId")
            player_id = data.get("playerId")
            print(f"[GAME STARTED] Game: {game_id}, Player: {player_id}")

            self.current_game_id = game_id
            self.current_player_id = player_id

            # Acknowledge back to Node (mirrors frontend emit)
            self.sio.emit("start-game", {"gameId": game_id, "playerId": player_id})
            print("↪️ Emitted start-game ack")

        @self.sio.on("frame:new")
        def on_frame_new(frame):
            """Handle single incoming frame"""
            game_id = frame.get("gameId")
            player_id = frame.get("playerId")
            frame_path = frame.get("path")

            if not frame_path:
                print("⚠️ Frame missing 'path'")
                return

            if frame_path in self.frame_cache:
                print(f"[AI] Skipping duplicate frame: {frame_path}")
                return

            self.frame_cache.add(frame_path)
            print(f"[FRAME RECEIVED] {frame_path}")

            # Process frame in background thread
            import threading
            thread = threading.Thread(
                target=self.process_frame_sync,
                args=(frame_path, game_id, player_id)
            )
            thread.daemon = True
            thread.start()

        @self.sio.on("ai:response")
        def on_ai_response(data):
            print(f"[AI RESPONSE RECEIVED] {data}")

        @self.sio.event
        def disconnect():
            print("❌ Disconnected from Node backend")
            self.ai_active = False

    def process_frame_sync(self, frame_path: str, game_id: str, player_id: str):
        """Process a single frame"""
        try:
            if not os.path.exists(frame_path):
                print(f"❌ Frame not found: {frame_path}")
                return

            with open(frame_path, "rb") as f:
                frame_bytes = f.read()

            print(f"[AI] Processing frame: {frame_path}")
            analysis_result = analyze_frame_batch([frame_bytes], TASK)

            ai_response = {
                "gameId": game_id,
                "playerId": player_id,
                "framePath": frame_path,
                "result": analysis_result,
                "processed_at": int(time.time() * 1000),
                "model_used": "gemini-2.5-flash-lite",
                "batch_processed": False,
            }

            self.sio.emit("ai:response", ai_response)
            print(f"[AI RESPONSE SENT] {frame_path}")

        except Exception as e:
            print(f"[AI ERROR] {e}", flush=True)
            import traceback
            traceback.print_exc()

    def connect_to_node(self):
        try:
            self.sio.connect(self.node_url, transports=["websocket", "polling"])
            print(f"🌐 Connecting to {self.node_url}...")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        if self.sio.connected:
            self.sio.disconnect()
            print("🔌 Disconnected from Node backend")


async def main():
    NODE_URL = "https://ss4j58hs-4440.inc1.devtunnels.ms"

    ai_backend = HybridAIBackend(NODE_URL)

    if ai_backend.connect_to_node():
        try:
            print("🚀 AI Engine running. Waiting for frames...")
            while ai_backend.ai_active:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down AI backend...")
        finally:
            ai_backend.disconnect()
    else:
        print("❌ Failed to connect to Node backend")


if __name__ == "__main__":
    asyncio.run(main())
