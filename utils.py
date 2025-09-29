
import threading

def send_api_request(command):
    return command

# Command functions — return response text + trigger API
def move_forward():
    threading.Thread(target=send_api_request, args=("move_forward",), daemon=True).start()
    return "Okay, moving forward."

def move_backward():
    threading.Thread(target=send_api_request, args=("move_backward",), daemon=True).start()
    return "Got it, moving backward."

def start_arvr():
    threading.Thread(target=send_api_request, args=("start",), daemon=True).start()
    return "Starting the AR VR session now."

def exit_arvr():
    threading.Thread(target=send_api_request, args=("exit",), daemon=True).start()
    return "Exiting the AR VR session."