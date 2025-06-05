import requests
import io
import random
import string
import time
import json
import os
from functools import wraps

def retry_api_call(max_retries=5, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for retry_count in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"An error occurred during {func.__name__} call: {e}")
                    if retry_count < max_retries - 1:
                        delay = base_delay * (2 ** retry_count)
                        print(f"Retrying {func.__name__} in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        print(f"Max retries reached for {func.__name__}. Failing...")
                        raise
        return wrapper
    return decorator

class VM:
    def __init__(self, vm_server_ip: str = "192.168.1.64", vm_server_port: int = 6969):
        # VM server configuration
        self.vm_server = f"http://{vm_server_ip}:{vm_server_port}"
    # VM Control Methods
    @retry_api_call()
    def screenshot(self, x: int = None, y: int = None, width: int = None, height: int = None) -> bytes:
        """Take a screenshot of the VM. Can specify region with x,y,width,height."""
        params = {}
        if all(v is not None for v in [x, y, width, height]):
            params = {'x': x, 'y': y, 'width': width, 'height': height}
        
        response = requests.get(f"{self.vm_server}/screenshot", params=params, timeout=10)
        response.raise_for_status()
        return response.content

    @retry_api_call()
    def move_to(self, x: int, y: int) -> dict:
        """Move mouse cursor to absolute position."""
        response = requests.get(f"{self.vm_server}/moveto", params={'x': x, 'y': y})
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def move_relative(self, direction: str, pixels: int = 10) -> dict:
        """Move mouse cursor relative to current position."""
        response = requests.get(f"{self.vm_server}/moverel", 
                              params={'direction': direction, 'pixels': pixels})
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def input(self, input_type: str, content: str | list, interval: float = 0.1) -> dict:
        """Send keyboard input (text or hotkeys)."""
        data = {
            'type': input_type,
            'content': content,
            'interval': interval
        }
        response = requests.post(f"{self.vm_server}/input", json=data)
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def scroll(self, direction: str, clicks: int = 1) -> dict:
        """Scroll the mouse wheel."""
        response = requests.get(f"{self.vm_server}/scroll", 
                              params={'direction': direction, 'clicks': clicks})
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def get_wmctrl_info(self) -> dict:
        """Get detailed window manager information (wmctrl -lG, active window, default apps)."""
        response = requests.get(f"{self.vm_server}/wmctrlinfo")
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def change_wmctrl_info(self, id: str) -> dict:
        """Change the focus to a specific window using its ID."""
        data = {'id': id}
        response = requests.post(f"{self.vm_server}/changewmctrlinfo", json=data)
        response.raise_for_status()
        return response.json()

    def run_operations(self, operations: list) -> list:
        """Execute a list of VM_TOOLS operations."""
        results = []
        for op in operations:
            op_type = op.get("type")
            # Parameters are now under 'parameters' key, not 'args'
            parameters = op.get("parameters", {}) 
            result = {"type": op_type, "success": False, "details": ""}
            try:
                if op_type == "action":
                    action_name = op.get("action_name")
                    if action_name == "moveto":
                        self.move_to(**parameters)
                    elif action_name == "moverel":
                        self.move_relative(**parameters)
                    elif action_name == "input":
                        # Map 'type' from parameters to 'input_type' for the method call
                        input_type_val = parameters.get("type")
                        content_val = parameters.get("content")
                        interval_val = parameters.get("interval", 0.1)
                        self.input(input_type=input_type_val, content=content_val, interval=interval_val)
                    elif action_name == "scroll":
                        self.scroll(**parameters)
                    elif action_name == "changewmctrlinfo":
                        self.change_wmctrl_info(**parameters)
                    elif action_name == "screenshot": # Although screenshots are usually not actions, handling for completeness
                        screenshot_bytes = self.screenshot(**parameters)
                        result["details"] = f"Captured screenshot of {len(screenshot_bytes)} bytes"
                    else:
                        result["details"] = f"Unknown action_name: {action_name}"
                        results.append(result)
                        continue # Skip to next operation if action_name is unknown
                    result["success"] = True
                elif op_type == "sleep":
                    duration_ms = op.get("duration_ms")
                    if duration_ms is not None and duration_ms > 0:
                        time.sleep(duration_ms / 1000) # Convert ms to seconds for time.sleep
                        result["success"] = True
                    else:
                        result["details"] = f"Invalid or missing duration_ms for sleep operation: {duration_ms}"
                else:
                    result["details"] = f"Unknown operation type: {op_type}"
            except Exception as e:
                result["details"] = f"Failed to execute {op_type} ({op.get('action_name', '')}): {str(e)}"
            results.append(result)
        return results