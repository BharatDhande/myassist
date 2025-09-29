
from utils import move_forward, move_backward, start_arvr, exit_arvr

COMMANDS = {
    # Forward
    "move forward": move_forward,
    "go forward": move_forward,
    "walk forward": move_forward,
    "step forward": move_forward,
    "forward": move_forward,
    "ahead": move_forward,
    "advance": move_forward,
    "proceed": move_forward,
    "next": move_forward,

    # Backward
    "move backward": move_backward,
    "go backward": move_backward,
    "walk back": move_backward,
    "step back": move_backward,
    "backward": move_backward,
    "back": move_backward,
    "reverse": move_backward,
    "retreat": move_backward,

    # Start
    "start": start_arvr,
    "begin": start_arvr,
    "launch": start_arvr,
    "initiate": start_arvr,
    "open": start_arvr,
    "run": start_arvr,
    "activate": start_arvr,
    "boot": start_arvr,

    # Exit
    "exit": exit_arvr,
    "quit": exit_arvr,
    "close": exit_arvr,
    "stop": exit_arvr,
    "terminate": exit_arvr,
    "shutdown": exit_arvr,
    "end": exit_arvr,
    "cancel": exit_arvr,
}

# Build reverse canonical map
CANONICAL_MAP = {
    "move_forward": ["move forward", "go forward", "walk forward", "step forward", "forward", "ahead", "advance", "proceed", "next"],
    "move_backward": ["move backward", "go backward", "walk back", "step back", "backward", "back", "reverse", "retreat"],
    "start_game": ["start", "begin", "launch", "initiate", "open", "run", "activate", "boot"],
    "exit_game": ["exit", "quit", "close", "stop", "terminate", "shutdown", "end", "cancel"],
}

def get_canonical_command(matched: str) -> str:
    for canonical, synonyms in CANONICAL_MAP.items():
        if matched in synonyms:
            return canonical
    return matched
