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
    def change_wmctrl_info(self, window_id: str) -> dict:
        """Change the focus to a specific window using its ID."""
        data = {'window_id': window_id}
        response = requests.post(f"{self.vm_server}/changewmctrlinfo", json=data)
        response.raise_for_status()
        return response.json()