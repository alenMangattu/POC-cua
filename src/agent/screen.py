import requests
import io
import random
import string
import time
import json
import os
import subprocess
from functools import wraps

# Import the analysis classes
from src.agent.vision_model import VisionModel

def retry_api_call(max_retries=5, base_delay=1, ignore_exceptions=()):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for retry_count in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if isinstance(e, ignore_exceptions):
                        print(f"Caught {type(e).__name__}, not retrying as it's in ignore_exceptions.")
                        raise # Re-raise the ignored exception immediately
                    else:
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
        return None
        
        """Get detailed window manager information (wmctrl -lG, active window, default apps)."""
        try:
            response = requests.get(f"{self.vm_server}/wmctrlinfo")
            
            # If the response is not successful, try to parse the error message
            if not response.ok: # Check if status code is 200-299
                try:
                    error_json = response.json()
                    error_message = error_json.get('error', f'HTTP Error {response.status_code}')
                    print(f"VM server returned an error (status {response.status_code}): {error_message}")
                    return {'success': False, 'error': error_message}
                except json.JSONDecodeError:
                    error_message = f"VM server returned non-JSON error (status {response.status_code}): {response.text}"
                    print(error_message)
                    return {'success': False, 'error': error_message}
            
            # If successful, proceed to parse the JSON content
            response_json = response.json()

            # Check if the VM server itself reported an xdotool error within a 200 OK response
            if not response_json.get('success', True) and \
               "xdo_get_active_window reported an error" in response_json.get('error', ''):
                print(f"Specific wmctrl active window error detected by VM server within 200 OK: {response_json.get('error')}")
                return {'success': False, 'error': response_json.get('error')}
            return response_json
        except requests.exceptions.RequestException as e:
            print(f"Network or HTTP error during get_wmctrl_info: {e}")
            raise # Re-raise for retry_api_call to handle
        except json.JSONDecodeError as e:
            print(f"JSON decode error from VM server response: {e}")
            raise # Re-raise for retry_api_call to handle
        except Exception as e:
            print(f"An unexpected error occurred in get_wmctrl_info: {e}")
            raise # Re-raise for retry_api_call to handle

    @retry_api_call()
    def change_wmctrl_info(self, id: str) -> dict:
        """Change the focus to a specific window using its ID."""
        data = {'id': id}
        response = requests.post(f"{self.vm_server}/changewmctrlinfo", json=data)
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.0) -> dict:
        """Perform a mouse click at specified coordinates."""
        data = {
            "x": x,
            "y": y,
            "button": button,
            "clicks": clicks,
            "interval": interval
        }
        response = requests.post(f"{self.vm_server}/click", json=data)
        response.raise_for_status()
        return response.json()

    @retry_api_call()
    def get_screen_resolution(self) -> dict:
        """Get the screen resolution (width and height) from the VM."""
        response = requests.get(f"{self.vm_server}/screenresolution")
        response.raise_for_status()
        return response.json()

    # This method will now orchestrate the scan logic by calling screenshot and then OmniParser/VisionModel
    @retry_api_call()
    def scan_screen(self, method: str, area_type: str, coordinates: list = None, window_id: str = None, vision_model_query: str = None) -> dict:
        """Perform a screen scan using specified method and area."""
        screenshot_data = None
        try:
            if area_type == "full":
                screenshot_data = self.screenshot()
            elif area_type == "window" and window_id:
                # Attempt to get specific window geometry for screenshot
                wmctrl_info = self.get_wmctrl_info()
                target_window = next((w for w in wmctrl_info.get('window_list', []) if w['id'] == window_id), None)
                if target_window and target_window.get('geometry'):
                    geo = target_window['geometry']
                    screenshot_data = self.screenshot(x=geo['x'], y=geo['y'], width=geo['width'], height=geo['height'])
                else:
                    print(f"Warning: Window ID {window_id} not found or no geometry. Taking full screenshot.")
                    screenshot_data = self.screenshot() # Fallback to full screenshot
            elif area_type == "region" and coordinates and len(coordinates) == 4:
                x, y, width, height = coordinates
                screenshot_data = self.screenshot(x=x, y=y, width=width, height=height)
            else:
                print(f"Invalid area_type ({area_type}) or coordinates/window_id. Taking full screenshot.")
                screenshot_data = self.screenshot() # Fallback

            if screenshot_data is None:
                return {"success": False, "error": "Failed to capture screenshot or screenshot data is empty."}

            if method == "Omni Parser":
                omni_parser = OmniParser()
                success, ui_classification, ui_elements = omni_parser.analyze_screenshot_data(screenshot_data)
                return {
                    "success": success,
                    "method": method,
                    "ui_classification": ui_classification,
                    "ui_elements": ui_elements,
                    "message": "Omni Parser analysis completed." if success else "Omni Parser analysis failed."
                }
            elif method == "Vision Model":
                if not vision_model_query:
                    return {"success": False, "error": "Vision Model method requires a vision_model_query.", "message": "Vision Model method requires a vision_model_query."}
                vision_model = VisionModel()
                vision_analysis = vision_model.analyze(screenshot_data, vision_model_query)
                return {
                    "success": True, # Assume success if analyze returns anything (analyze method has its own retry)
                    "method": method,
                    "vision_analysis": vision_analysis,
                    "message": "Vision Model analysis completed."
                }
            elif method == "Omni Parser + Vision Model":
                omni_parser = OmniParser()
                success_omni, ui_classification, ui_elements = omni_parser.analyze_screenshot_data(screenshot_data)
                
                vision_analysis = ""
                if success_omni and vision_model_query:
                    vision_model = VisionModel()
                    vision_analysis = vision_model.analyze(screenshot_data, vision_model_query)
                
                return {
                    "success": success_omni, # Overall success depends primarily on OmniParser here
                    "method": method,
                    "ui_classification": ui_classification,
                    "ui_elements": ui_elements,
                    "vision_analysis": vision_analysis,
                    "message": "Omni Parser + Vision Model analysis completed." if success_omni else "Omni Parser + Vision Model analysis failed."
                }
            else:
                return {"success": False, "error": f"Unknown scan method: {method}"}
        except Exception as e:
            print(f"Error during scan_screen: {e}")
            return {"success": False, "error": str(e)}

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
                    elif action_name == "click":
                        self.click(**parameters)
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
                elif op_type == "SCAN":
                    scan_result = self.scan_screen(**parameters)
                    result["success"] = scan_result.get("success", False)
                    result["details"] = scan_result
                else:
                    result["details"] = f"Unknown operation type: {op_type}"
            except Exception as e:
                result["details"] = f"Failed to execute {op_type} ({op.get('action_name', '')}): {str(e)}"
            results.append(result)
        return results