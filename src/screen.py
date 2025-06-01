import requests
import io
import random
import string
import time
import json
import os

class VM:
    def __init__(self, vm_server_ip: str = "192.168.1.64", vm_server_port: int = 6969, 
                 omniparser_url: str = "https://d2e4c8ed4c4b79d4b9.gradio.live/"):
        # VM server configuration
        self.vm_server = f"http://{vm_server_ip}:{vm_server_port}"
        
        # OmniParser configuration
        self.omniparser_url = omniparser_url.rstrip('/')
        self.session = requests.Session()
        
        # OmniParser default parameters
        self.box_threshold = 0.05
        self.iou_threshold = 0.1
        self.use_paddle_ocr = True
        self.icon_detect_image_size = 640
        
        # Gradio API constants
        self.fn_index = 0
        self.trigger_id = 9

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

    # OmniParser Methods
    def _generate_id(self, k=11) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))

    def upload_image_to_gradio(self, image_data: bytes, filename: str = "screenshot.png") -> tuple[str | None, str | None, str | None, int | None]:
        """Uploads image to Gradio. Returns (server_local_path, public_file_url, upload_id, file_size)."""
        upload_id = self._generate_id()
        files = {'files': (filename, io.BytesIO(image_data), 'image/png')}
        upload_url = f"{self.omniparser_url}/gradio_api/upload"
        params = {'upload_id': upload_id}
        
        try:
            response = self.session.post(upload_url, params=params, files=files, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            server_local_path = result[0] if result and isinstance(result, list) and len(result) > 0 else None
            if server_local_path:
                file_size = len(image_data)
                public_file_url = f"{self.omniparser_url}/gradio_api/file={server_local_path.lstrip('/')}"
                return server_local_path, public_file_url, upload_id, file_size
            else:
                print(f"✗ Upload response did not contain expected file path")
                return None, None, upload_id, None
        except Exception as e:
            print(f"✗ Error during upload: {str(e)}")
            if isinstance(e, requests.exceptions.RequestException) and e.response:
                print(f"Error Response: {e.response.status_code} - {e.response.text}")
            return None, None, upload_id, None

    def start_omniparser_processing(self, server_local_path: str, public_file_url: str, 
                                  orig_name: str, file_size: int,
                                  box_threshold: float = None,
                                  iou_threshold: float = None,
                                  use_paddle_ocr: bool = None,
                                  icon_detect_image_size: int = None) -> tuple[str | None, str | None]:
        """Start OmniParser processing via queue/join. Returns (session_hash, event_id)."""
        session_hash = self._generate_id()
        
        # Use provided values or fall back to instance defaults
        box_threshold = box_threshold if box_threshold is not None else self.box_threshold
        iou_threshold = iou_threshold if iou_threshold is not None else self.iou_threshold
        use_paddle_ocr = use_paddle_ocr if use_paddle_ocr is not None else self.use_paddle_ocr
        icon_detect_image_size = icon_detect_image_size if icon_detect_image_size is not None else self.icon_detect_image_size
        
        payload = {
            "data": [{
                "path": server_local_path,
                "url": public_file_url,
                "orig_name": orig_name,
                "size": file_size,
                "mime_type": "image/png",
                "meta": {"_type": "gradio.FileData"}
            },
            box_threshold,
            iou_threshold,
            use_paddle_ocr,
            icon_detect_image_size],
            "event_data": None,
            "fn_index": self.fn_index,
            "trigger_id": self.trigger_id,
            "session_hash": session_hash
        }
        
        queue_join_url = f"{self.omniparser_url}/gradio_api/queue/join"
        
        try:
            response = self.session.post(f"{queue_join_url}?", json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            event_id = result.get("event_id")
            if event_id:
                return session_hash, event_id
            else:
                print(f"✗ Queue join response did not contain event_id")
                return None, None
        except Exception as e:
            print(f"✗ Error joining queue: {str(e)}")
            if isinstance(e, requests.exceptions.RequestException) and e.response:
                print(f"Error Response: {e.response.status_code} - {e.response.text}")
            return None, None

    def get_queue_results(self, session_hash: str, event_id: str) -> dict | None:
        """Get results from queue/data endpoint using session_hash."""
        if not session_hash or not event_id:
            print("✗ Missing session_hash or event_id for getting queue results.")
            return None

        queue_data_url = f"{self.omniparser_url}/gradio_api/queue/data"
        params = {'session_hash': session_hash}
        
        try:
            with self.session.get(queue_data_url, params=params, stream=True, timeout=300) as response:
                response.raise_for_status()
                print("Waiting for processing...")
                
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        line = line[len("data: "):]
                    
                    try:
                        data = json.loads(line)
                        msg_type = data.get("msg")
                        
                        if msg_type == "estimation":
                            rank = data.get('rank', 'unknown')
                            queue_size = data.get('queue_size', 'unknown')
                            eta = data.get('rank_eta')
                            eta_str = f"{eta:.1f}s" if eta is not None else "N/A"
                            print(f"Queue Position: {rank}/{queue_size}, ETA: {eta_str}")
                            
                        elif msg_type == "process_starts":
                            print("Processing started...")
                            
                        elif msg_type == "process_completed":
                            output = data.get("output", {})
                            
                            if isinstance(output, dict) and "data" in output and len(output["data"]) >= 2:
                                return {
                                    "success": True,
                                    "processed_image_info": output["data"][0],
                                    "ui_classification": output["data"][1],
                                    "event_id": event_id
                                }
                            else:
                                print(f"✗ Unexpected output format")
                                return {
                                    "success": False,
                                    "error": "Unexpected output format",
                                    "raw_output": output,
                                    "event_id": event_id
                                }
                    except json.JSONDecodeError as e:
                        print(f"✗ JSON decode error: {e}")
                    except Exception as e:
                        print(f"✗ Error processing stream data: {e}")
                        
                print("Queue data stream ended without completion")
                return {"success": False, "error": "Stream ended without completion", "event_id": event_id}
                
        except Exception as e:
            print(f"✗ Error getting queue results: {str(e)}")
            if isinstance(e, requests.exceptions.RequestException) and e.response:
                print(f"Error Response: {e.response.status_code} - {e.response.text}")
            return {"success": False, "error": str(e), "event_id": event_id}

    def parse_ui_elements(self, ui_classification: str) -> list:
        """Parse UI elements from classification output."""
        elements = []
        if not isinstance(ui_classification, str) or not ui_classification.strip():
            print("Warning: UI classification data is empty or not a string")
            return elements
            
        for line in ui_classification.strip().split('\n'):
            if not line.strip().startswith('icon'):
                continue
                
            try:
                parts = line.split(':', 1)
                if len(parts) != 2:
                    continue
                    
                icon_id = parts[0].replace('icon', '').strip()
                dict_str = parts[1].strip()
                dict_str = dict_str.replace("'", '"').replace("False", "false").replace("True", "true").replace("None", "null")
                
                data = json.loads(dict_str)
                elements.append({
                    'id': int(icon_id),
                    'type': data.get('type'),
                    'bbox': data.get('bbox'),
                    'interactivity': data.get('interactivity'),
                    'content': data.get('content')
                })
            except Exception as e:
                print(f"Warning: Failed to parse UI element: {line}. Error: {e}")
                
        return elements

    def analyze_screenshot(self, save_locally: bool = False) -> tuple[bool, str, list]:
        """Take a screenshot and analyze it with OmniParser.
        Returns:
            tuple: (success: bool, ui_classification: str, ui_elements: list)
            - success: Whether the analysis was successful
            - ui_classification: Raw classification output string
            - ui_elements: List of parsed UI elements
        """
        try:
            screenshot_data = self.screenshot()
            print(f"Screenshot captured: {len(screenshot_data)} bytes")
            
            if save_locally:
                with open("screenshot.png", "wb") as f:
                    f.write(screenshot_data)
        except Exception as e:
            print(f"✗ Screenshot capture failed: {e}")
            return False, "", []

        server_path, public_url, upload_id, file_size = self.upload_image_to_gradio(screenshot_data)
        if not all([server_path, public_url, file_size]):
            print("✗ Upload failed")
            return False, "", []

        session_hash, event_id = self.start_omniparser_processing(
            server_path, public_url, "screenshot.png", file_size
        )
        if not session_hash or not event_id:
            print("✗ Failed to start processing")
            return False, "", []

        results = self.get_queue_results(session_hash, event_id)
        
        if results and results.get("success"):
            ui_class = results.get("ui_classification", "")
            
            if save_locally:
                try:
                    with open("ui_classification.txt", "w") as f:
                        f.write(ui_class)
                except Exception as e:
                    print(f"✗ Failed to save classification: {e}")
                
            elements = self.parse_ui_elements(ui_class)
            print(f"Found {len(elements)} UI elements")
            return True, ui_class, elements
        else:
            print("✗ Processing failed")
            if results:
                print(f"Error: {results.get('error', 'Unknown')}")
                if 'raw_output' in results:
                    print(f"Server output: {results['raw_output']}")
            return False, "", []