# services/voice_command_service.py
"""
Voice command processing service
"""
from fuzzywuzzy import process
from typing import Dict, Any

from core.config import settings
from core.logging_config import get_logger
from utils.command_handlers import CommandHandlers
from utils.command_registry import CommandRegistry


logger = get_logger(__name__)


class VoiceCommandService:
    """Service for processing voice commands"""
    
    def __init__(self):
        self.command_registry = CommandRegistry()
        self.command_handlers = CommandHandlers()
        self.threshold = settings.FUZZY_THRESHOLD
        
        # Register all commands
        self._register_commands()
    
    def _register_commands(self):
        """Register all available commands"""
        
        # Forward commands
        forward_commands = [
            "move forward", "go forward", "walk forward", 
            "step forward", "forward", "ahead", "advance", 
            "proceed", "next"
        ]
        for cmd in forward_commands:
            self.command_registry.register(
                cmd, 
                "move_forward", 
                self.command_handlers.move_forward
            )
        
        # Backward commands
        backward_commands = [
            "move backward", "go backward", "walk back", 
            "step back", "backward", "back", "reverse", "retreat"
        ]
        for cmd in backward_commands:
            self.command_registry.register(
                cmd, 
                "move_backward", 
                self.command_handlers.move_backward
            )
        
        # Start commands
        start_commands = [
            "start", "begin", "launch", "initiate", 
            "open", "run", "activate", "boot"
        ]
        for cmd in start_commands:
            self.command_registry.register(
                cmd, 
                "start_game", 
                self.command_handlers.start_arvr
            )
        
        # Exit commands
        exit_commands = [
            "exit", "quit", "close", "stop", 
            "terminate", "shutdown", "end", "cancel"
        ]
        for cmd in exit_commands:
            self.command_registry.register(
                cmd, 
                "exit_game", 
                self.command_handlers.exit_arvr
            )
    
    def process_command(self, user_text: str) -> Dict[str, Any]:
        """
        Process a voice command using fuzzy matching
        
        Args:
            user_text: User's voice input text
            
        Returns:
            Dict containing processing result
        """
        try:
            # Get all registered command phrases
            command_phrases = self.command_registry.get_all_phrases()
            
            # Fuzzy match
            match, score = process.extractOne(user_text, command_phrases)
            
            logger.info(f"[VOICE] Match: '{match}' (score: {score})")
            
            if score >= self.threshold:
                # Get command details and execute
                canonical, handler = self.command_registry.get_command(match)
                response_text = handler()
                
                return {
                    "status": "success",
                    "suggestion": response_text,
                    "canonical": canonical,
                    "score": score
                }
            else:
                # No good match found
                canonical, _ = self.command_registry.get_command(match)
                
                return {
                    "status": "no_match",
                    "suggestion": "Sorry, I didn't catch that.",
                    "best_guess": canonical,
                    "score": score
                }
                
        except Exception as e:
            logger.error(f"[VOICE] Command processing error: {e}")
            raise