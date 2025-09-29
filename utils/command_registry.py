# utils/command_registry.py
"""
Command registry for managing voice command mappings
"""
from typing import Dict, Callable, Tuple, List
from core.logging_config import get_logger

logger = get_logger(__name__)


class CommandRegistry:
    """Registry for managing command phrases and handlers"""
    
    def __init__(self):
        self._commands: Dict[str, Tuple[str, Callable]] = {}
    
    def register(
        self, 
        phrase: str, 
        canonical: str, 
        handler: Callable
    ):
        """
        Register a command phrase
        
        Args:
            phrase: Voice command phrase (e.g., "move forward")
            canonical: Canonical command name (e.g., "move_forward")
            handler: Function to execute for this command
        """
        self._commands[phrase] = (canonical, handler)
        logger.debug(f"[REGISTRY] Registered: '{phrase}' -> {canonical}")
    
    def get_command(self, phrase: str) -> Tuple[str, Callable]:
        """
        Get command details for a phrase
        
        Args:
            phrase: Voice command phrase
            
        Returns:
            Tuple of (canonical_name, handler_function)
        """
        return self._commands.get(phrase, (phrase, lambda: "Unknown command"))
    
    def get_all_phrases(self) -> List[str]:
        """
        Get all registered command phrases
        
        Returns:
            List of command phrases
        """
        return list(self._commands.keys())
    
    def get_canonical_name(self, phrase: str) -> str:
        """
        Get canonical name for a phrase
        
        Args:
            phrase: Voice command phrase
            
        Returns:
            Canonical command name
        """
        canonical, _ = self.get_command(phrase)
        return canonical