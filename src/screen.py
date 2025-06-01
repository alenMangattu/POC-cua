import requests
import io
import random
import string
import time
import json
import os

class VM:
    def __init__(self, vm_server_ip: str = "192.168.1.64", vm_server_port: int = 6969):
        # VM server configuration
        self.vm_server = f"http://{vm_server_ip}:{vm_server_port}"
    # VM Control Methods
    def screenshot(self, x: int = None, y: int = None, width: int = None, height: int = None) -> bytes:
        """Take a screenshot of the VM. Can specify region with x,y,width,height."""
        params = {}
        if all(v is not None for v in [x, y, width, height]):
            params = {'x': x, 'y': y, 'width': width, 'height': height}
        
        response = requests.get(f"{self.vm_server}/screenshot", params=params, timeout=10)
        response.raise_for_status()
        return response.content

    def move_to(self, x: int, y: int) -> dict:
        """Move mouse cursor to absolute position."""
        response = requests.get(f"{self.vm_server}/moveto", params={'x': x, 'y': y})
        response.raise_for_status()
        return response.json()

    def move_relative(self, direction: str, pixels: int = 10) -> dict:
        """Move mouse cursor relative to current position."""
        response = requests.get(f"{self.vm_server}/moverel", 
                              params={'direction': direction, 'pixels': pixels})
        response.raise_for_status()
        return response.json()

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

    def scroll(self, direction: str, clicks: int = 1) -> dict:
        """Scroll the mouse wheel."""
        response = requests.get(f"{self.vm_server}/scroll", 
                              params={'direction': direction, 'clicks': clicks})
        response.raise_for_status()
        return response.json()