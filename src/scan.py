import requests
import io
import random
import string
import time
import json
import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import re


class OmniParser:
    def __init__(self, omniparser_url: str = None):
        # OmniParser configuration
        load_dotenv()
        self.omniparser_url = omniparser_url.rstrip('/') if omniparser_url else os.getenv("OMNI_URL", "").rstrip('/')
        self.session = requests.Session()
        
        # OmniParser default parameters
        self.box_threshold = 0.01
        self.iou_threshold = 0.01
        self.use_paddle_ocr = False
        self.icon_detect_image_size = 640
        self.process_delay = float(os.getenv("OMNI_PROCESS_DELAY", 0.5)) # New parameter for flow control
        
        # Gradio API constants
        self.fn_index = 0
        self.trigger_id = 9

    def _generate_id(self, k=11) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=k))

    def upload_image_to_gradio(self, image_data: bytes, filename: str = "screenshot.png") -> tuple[str | None, str | None, str | None, int | None]:
        """Uploads image to Gradio. Returns (server_local_path, public_file_url, upload_id, file_size)."""
        upload_id = self._generate_id()
        files = {'files': (filename, io.BytesIO(image_data), 'image/png')}
        upload_url = f"{self.omniparser_url}/gradio_api/upload"
        params = {'upload_id': upload_id}
        
        print(f"Attempting to upload image of size: {len(image_data)} bytes")
        try:
            response = self.session.post(upload_url, params=params, files=files, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            server_local_path = result[0] if result and isinstance(result, list) and len(result) > 0 else None
            if server_local_path:
                file_size = len(image_data)
                public_file_url = f"{self.omniparser_url}/gradio_api/file={server_local_path.lstrip('/')}"
                print(f"✓ Uploaded image to Gradio. Public URL: {public_file_url}")
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

    def _draw_ui_elements_on_screenshot(self, screenshot_data: bytes, ui_elements: list, ui_classification: str, output_filename: str = "annotated_screenshot.png"):
        """Draws bounding boxes and text from UI elements on the screenshot and saves it."""
        try:
            image = Image.open(io.BytesIO(screenshot_data))
            draw = ImageDraw.Draw(image)

            # You may need to specify a font path if default 'arial.ttf' is not found
            # For example: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except IOError:
                font = ImageFont.load_default() # Fallback to default font

            # Draw bounding boxes and text for UI elements
            for element in ui_elements:
                if 'bbox' in element and len(element['bbox']) == 4:
                    x_min, y_min, x_max, y_max = element['bbox']
                    draw.rectangle([x_min, y_min, x_max, y_max], outline="red", width=2)
                    content = element.get('content', '')
                    # Draw text slightly above the bounding box
                    draw.text((x_min, y_min - 10), content, fill="red", font=font)
            
            # Add UI Classification as text on the image
            # You might want to adjust the position based on your screenshot layout
            # For simplicity, placing it at the top-left or bottom-left
            # current_y_offset = 10
            # for line in ui_classification.split('\n'):
            #    draw.text((10, current_y_offset), line, fill="blue", font=font)
            #    current_y_offset += 15 # Adjust line height

            image.save(output_filename)
            print(f"✓ Annotated screenshot saved to {output_filename}")
        except Exception as e:
            print(f"✗ Error drawing UI elements on screenshot: {e}")

    def parse_ui_elements(self, ui_classification: str, screen_width: int = None, screen_height: int = None) -> tuple[list, str]:
        """Parse UI elements from classification output, calculate absolute bounding box coordinates, and reconstruct the classification string with absolute bboxes."""
        elements = []
        new_ui_classification_lines = []

        if not isinstance(ui_classification, str) or not ui_classification.strip():
            print("Warning: UI classification data is empty or not a string")
            return elements, ""
            
        for line in ui_classification.strip().split('\n'):
            # print(f"[DEBUG] Processing line: {line}")
            
            # Check if line contains a dictionary structure with bbox
            if ':' in line and '{' in line and 'bbox' in line:
                try:
                    parts = line.split(':', 1)
                    if len(parts) != 2:
                        new_ui_classification_lines.append(line)
                        continue
                        
                    element_id = parts[0].strip()
                    dict_str = parts[1].strip()
                    # print(f"[DEBUG] Original dict_str: {dict_str}")
                    
                    # More robust quote handling - escape all quotes properly for JSON
                    # First, find all content values and escape quotes within them
                    def escape_content_quotes(match):
                        content_value = match.group(1)
                        # Escape any existing backslashes first
                        content_value = content_value.replace('\\', '\\\\')
                        # Then escape quotes
                        content_value = content_value.replace('"', '\\"')
                        content_value = content_value.replace("'", "\\'")
                        return f'"content": "{content_value}"'
                    
                    # Replace content values with properly escaped versions
                    dict_str = re.sub(r"'content':\s*['\"]([^'\"]*(?:['\"][^'\"]*)*)['\"]", escape_content_quotes, dict_str)
                    
                    # Then do the standard replacements
                    dict_str = dict_str.replace("'", '"').replace("False", "false").replace("True", "true").replace("None", "null")
                    # print(f"[DEBUG] Modified dict_str for JSON: {dict_str}")
                    
                    data = json.loads(dict_str)
                    # print(f"[DEBUG] Parsed JSON data: {data}")
                    
                    # Create element with original bbox
                    element = {
                        'id': int(element_id.replace('icon', '').strip()) if element_id.startswith('icon') else len(elements),
                        'type': data.get('type'),
                        'bbox': data.get('bbox'), # Store original normalized bbox
                        # 'interactivity': data.get('interactivity'),
                        'content': data.get('content')
                    }

                    # If content is "M0,0L9,0 4.5,5z", skip this element
                    if element.get('content') == "M0,0L9,0 4.5,5z":
                        continue
                    
                    # Remove 'interactivity' from the data dictionary before reconstruction
                    if 'interactivity' in data:
                        del data['interactivity']
                    
                    # Calculate absolute bbox and update element's 'bbox' for the elements list
                    if 'bbox' in data and screen_width and screen_height:
                        # Ensure bbox is a list of numbers, not a string
                        bbox_data = data['bbox']
                        # print(f"[DEBUG] Raw bbox_data: {bbox_data}, Type: {type(bbox_data)}")
                        if isinstance(bbox_data, str):
                            try:
                                # Attempt to parse string representation like "0.1, 0.2, 0.3, 0.4"
                                bbox_data = [float(x.strip()) for x in bbox_data.split(',')]
                            except ValueError:
                                print(f"Warning: Could not parse bbox string '{bbox_data}'. Skipping element.")
                                continue # Skip this element if bbox string is malformed
                        
                        if not isinstance(bbox_data, list) or len(bbox_data) != 4:
                            print(f"Warning: Bbox data is not a valid list of 4 numbers: {bbox_data}. Skipping element.")
                            continue # Skip if bbox is not a list of 4 numbers after parsing
                            
                        x_min_percent, y_min_percent, x_max_percent, y_max_percent = bbox_data
                        abs_bbox = [
                            int(x_min_percent * screen_width),
                            int(y_min_percent * screen_height),
                            int(x_max_percent * screen_width),
                            int(y_max_percent * screen_height)
                        ]
                        element['bbox'] = abs_bbox # Update bbox to absolute for the `elements` list
                        
                        # Also update the 'bbox' in the `data` dictionary to be used for reconstruction of the classification string
                        data['bbox'] = abs_bbox
                        # print(f"[DEBUG] Absolute bbox calculated: {abs_bbox}")
                    
                    elements.append(element)
                    
                    # Reconstruct the line for new_ui_classification_lines
                    reconstructed_dict_str = json.dumps(data)
                    reconstructed_dict_str = reconstructed_dict_str.replace('false', 'False').replace('true', 'True').replace('null', 'None')
                    new_ui_classification_lines.append(f"{element_id}: {reconstructed_dict_str}")

                except Exception as e:
                    print(f"Warning: Failed to parse UI element: {line}. Error: {e}")
                    new_ui_classification_lines.append(line) # Append original line if parsing fails
            else:
                # Line doesn't contain bbox data, just append as-is
                new_ui_classification_lines.append(line)

        return elements, "\n".join(new_ui_classification_lines)

    def analyze_screenshot_data(self, screenshot_data: bytes, screen_width: int, screen_height: int, save_locally: bool = False) -> tuple[bool, str, str]:
        """Analyze screenshot data with OmniParser.
        Args:
            screenshot_data: Bytes of the screenshot image.
            screen_width: Width of the screen in pixels.
            screen_height: Height of the screen in pixels.
            save_locally: Whether to save intermediate files locally.
        Returns:
            tuple: (success: bool, ui_classification_with_pixels: str, ui_elements_json: str)
        """
        if save_locally: # Added for consistency if screenshot is passed directly
            try:
                with open("screenshot.png", "wb") as f:
                    f.write(screenshot_data)
            except Exception as e:
                print(f"✗ Failed to save screenshot: {e}")

        max_retries = 5
        base_delay = 1  # seconds

        for retry_count in range(max_retries):
            try:
                server_path, public_url, upload_id, file_size = self.upload_image_to_gradio(screenshot_data)
                if not all([server_path, public_url, file_size]):
                    raise Exception("Upload failed")
                time.sleep(self.process_delay) # Introduce delay after upload

                session_hash, event_id = self.start_omniparser_processing(
                    server_path, public_url, "screenshot.png", file_size
                )
                if not session_hash or not event_id:
                    raise Exception("Failed to start processing")
                time.sleep(self.process_delay) # Introduce delay after starting processing

                results = self.get_queue_results(session_hash, event_id)
                
                if results and results.get("success"):
                    ui_class_raw = results.get("ui_classification", "")
                    
                    if save_locally:
                        try:
                            with open("ui_classification_raw.txt", "w") as f:
                                f.write(ui_class_raw)
                        except Exception as e:
                            print(f"✗ Failed to save raw classification: {e}")
                        
                    elements, ui_class_with_pixels = self.parse_ui_elements(ui_class_raw, screen_width, screen_height)
                    
                    if save_locally:
                        try:
                            with open("ui_classification.txt", "w") as f:
                                f.write(ui_class_with_pixels)
                            with open("ui_elements.json", "w") as f:
                                f.write(json.dumps(elements, indent=4))
                        except Exception as e:
                            print(f"✗ Failed to save processed classification or elements: {e}")
                    
                    # Draw and save annotated screenshot
                    self._draw_ui_elements_on_screenshot(screenshot_data, elements, ui_class_with_pixels)
                        
                    print(f"Found {len(elements)} UI elements")
                    return True, ui_class_with_pixels, json.dumps(elements)
                else:
                    error_message = results.get('error', 'Unknown error') if results else 'Unknown error'
                    if 'raw_output' in results:
                        error_message += f" Server output: {results['raw_output']}"
                    raise Exception(f"Processing failed: {error_message}")

            except Exception as e:
                print(f"An error occurred during OmniParser analysis: {e}")
                if retry_count < max_retries - 1:
                    delay = base_delay * (2 ** retry_count)
                    print(f"Retrying OmniParser analysis in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("Max retries reached for OmniParser analysis. Failing...")
                    return False, "", ""
