# utils/command_handlers.py
"""
Command handler functions for voice commands
"""
import threading
import requests
from typing import Optional
from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


class CommandHandlers:
    """Handlers for executing voice commands"""
    
    def __init__(self, api_url: Optional[str] = None):
        """
        Initialize command handlers
        
        Args:
            api_url: URL of AR/VR API endpoint (optional)
        """
        self.api_url = api_url
    
    def _send_api_request(self, command: str):
        """
        Send command to AR/VR API
        
        Args:
            command: Command to send
        """
        try:
            if self.api_url:
                logger.info(f"[API] Sending command: {command}")
                response = requests.post(
                    self.api_url,
                    json={"command": command},
                    timeout=5
                )
                response.raise_for_status()
                logger.info(f"[API] Command sent successfully: {command}")
            else:
                logger.debug(f"[API] Mock command: {command}")
        except Exception as e:
            logger.error(f"[API] Error sending command: {e}")
    
    def move_forward(self) -> str:
        """Handle move forward command"""
        threading.Thread(
            target=self._send_api_request, 
            args=("move_forward",), 
            daemon=True
        ).start()
        return "Okay, moving forward."
    
    def move_backward(self) -> str:
        """Handle move backward command"""
        threading.Thread(
            target=self._send_api_request, 
            args=("move_backward",), 
            daemon=True
        ).start()
        return "Got it, moving backward."
    
    def start_arvr(self) -> str:
        """Handle start AR/VR command"""
        threading.Thread(
            target=self._send_api_request, 
            args=("start",), 
            daemon=True
        ).start()
        return "Starting the AR VR session now."
    
    def exit_arvr(self) -> str:
        """Handle exit AR/VR command"""
        threading.Thread(
            target=self._send_api_request, 
            args=("exit",), 
            daemon=True
        ).start()
        return "Exiting the AR VR session."