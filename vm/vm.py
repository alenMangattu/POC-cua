from flask import Flask, send_file, request
import subprocess
import io
import os
from PIL import Image
import pyautogui
import time
 
app = Flask(__name__)
 
@app.route('/screenshot', methods=['GET'])
def screenshot():
    try:
        # Get parameters from the request
        x = request.args.get('x', type=int)
        y = request.args.get('y', type=int)
        width = request.args.get('width', type=int)
        height = request.args.get('height', type=int)
 
        # Temp filename
        temp_filename = "/tmp/screenshot.png"
 
        if all([x is not None, y is not None, width is not None, height is not None]):
            # Capture screenshot of specific region using scrot
            subprocess.run(['scrot', '-a', f'{x},{y},{width},{height}', temp_filename], check=True)
        else:
            # Capture full screenshot if parameters are missing
            subprocess.run(['scrot', temp_filename], check=True)
 
        # Open the image and load it into memory
        with open(temp_filename, 'rb') as f:
            img_bytes = io.BytesIO(f.read())
 
        # Optionally delete the temp file
        os.remove(temp_filename)
 
        # Return as image/png
        img_bytes.seek(0)
        return send_file(img_bytes, mimetype='image/png', download_name='screenshot.png')
 
    except subprocess.CalledProcessError as e:
        return {'error': f"scrot failed: {str(e)}"}, 500
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/moveto', methods=['GET'])
def move_to():
    try:
        x = request.args.get('x', type=int)
        y = request.args.get('y', type=int)
 
        if x is None or y is None:
            return {'error': 'x and y coordinates are required'}, 400

        pyautogui.moveTo(x, y)
        return {'success': True, 'position': {'x': x, 'y': y}}
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/moverel', methods=['GET'])
def move_relative():
    try:
        direction = request.args.get('direction')
        pixels = request.args.get('pixels', type=int, default=10)
 
        if direction not in ['up', 'down', 'left', 'right', 'upleft', 'upright', 'downleft', 'downright']:
            return {'error': 'Invalid direction'}, 400
 
        moves = {
            'up': (0, -pixels),
            'down': (0, pixels),
            'left': (-pixels, 0),
            'right': (pixels, 0),
            'upleft': (-pixels, -pixels),
            'upright': (pixels, -pixels),
            'downleft': (-pixels, pixels),
            'downright': (pixels, pixels)
        }
 
        x_move, y_move = moves[direction]
        pyautogui.moveRel(x_move, y_move)
        current_pos = pyautogui.position()
        return {'success': True, 'position': {'x': current_pos.x, 'y': current_pos.y}}
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/input', methods=['POST'])
def handle_input():
    try:
        data = request.get_json()
        input_type = data.get('type', 'text')  # 'text' or 'hotkey'
        content = data.get('content')
        interval = data.get('interval', 0.1)  # Time between keystrokes
 
        if not content:
            return {'error': 'content is required'}, 400
 
        if input_type == 'text':
            # Handle regular text typing
            pyautogui.write(content, interval=interval)
            print(f"Typed text: {content}")
            return {'success': True, 'type': 'text', 'typed': content}
 
        elif input_type == 'hotkey':
            # Define a mapping for common key name variations
            key_name_map = {
                "control": "ctrl",
                "alt": "alt",
                "shift": "shift",
                "caps lock": "capslock",
                "escape": "esc",
                "return": "enter",
                "pagedown": "pgdn",
                "pageup": "pgup",
                "printscreen": "prntscrn",
                "spacebar": "space",
                "super": "win",
                "windows": "win",
                "command": "win", # For macOS command key
                "option": "alt" # For macOS option key
            }

            def normalize_key(key):
                return key_name_map.get(key.lower(), key.lower())

            if isinstance(content, list):
                # Normalize hotkey combinations
                normalized_content = [normalize_key(key) for key in content]
                pyautogui.hotkey(*normalized_content)
                print(f"Pressed hotkey: {normalized_content}")
                return {'success': True, 'type': 'hotkey', 'keys_pressed': normalized_content}
            else:
                # Normalize single key press
                normalized_content = normalize_key(content)
                pyautogui.press(normalized_content)
                print(f"Pressed key: {normalized_content}")
                return {'success': True, 'type': 'hotkey', 'key_pressed': normalized_content}
 
        else:
            return {'error': 'Invalid input type. Must be either "text" or "hotkey"'}, 400
 
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/scroll', methods=['GET'])
def scroll():
    try:
        clicks = request.args.get('clicks', type=int, default=1)
        direction = request.args.get('direction')
 
        if direction not in ['up', 'down']:
            return {'error': 'direction must be either "up" or "down"'}, 400
 
        if direction == 'up':
            pyautogui.scroll(clicks)
            print(f"Scrolled up by {clicks} clicks")
        else:
            pyautogui.scroll(-clicks)
            print(f"Scrolled down by {clicks} clicks")
 
        return {'success': True, 'direction': direction, 'clicks': clicks}
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/screenresolution', methods=['GET'])
def get_screen_resolution():
    try:
        width, height = pyautogui.size()
        return {'success': True, 'width': width, 'height': height}
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/wmctrlinfo', methods=['GET'])
def get_wmctrl_info():
    try:
        # Get window info with full titles from wmctrl -l
        wmctrl_l_result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True, check=True)
        # Get window info with geometry from wmctrl -lG
        wmctrl_lG_result = subprocess.run(['wmctrl', '-lG'], capture_output=True, text=True, check=True)

        titles_by_id = {}
        for line in wmctrl_l_result.stdout.strip().split('\n'):
            if line:
                # wmctrl -l output format: <window ID> <desktop ID> <client machine> <title>
                # Split by whitespace, max 3 splits to get 4 parts (ID, desktop, client, title)
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    window_id = parts[0]
                    # The title is the last part, which contains spaces
                    title = parts[3].strip()
                    titles_by_id[window_id] = title

        # Get active window ID
        active_window_cmd = "xdotool getactivewindow"
        active_window_id_raw = subprocess.run(active_window_cmd, shell=True, capture_output=True, text=True, check=True).stdout.strip()
        active_window_id = f"0x{int(active_window_id_raw, 10):08x}" if active_window_id_raw else ""


        parsed_window_list = []
        parsed_active_window = {}

        # Parse wmctrl -lG output for geometry and desktop, then merge titles
        for line in wmctrl_lG_result.stdout.strip().split('\n'):
            if line:
                # wmctrl -lG output format: <window ID> <desktop ID> <x> <y> <width> <height> <client machine> <title (potentially truncated)>
                # Split by whitespace, max 6 splits to get the first 7 parts (ID to client machine)
                parts = line.split(None, 6)
                if len(parts) >= 7:
                    try:
                        window_id = parts[0]
                        desktop = int(parts[1])
                        geometry_x = int(parts[2])
                        geometry_y = int(parts[3])
                        geometry_width = int(parts[4])
                        geometry_height = int(parts[5])

                        # Get the full title from the titles_by_id map
                        title = titles_by_id.get(window_id, "N/A") # Default to "N/A" if title not found

                        window_data = {
                            'id': window_id,
                            'desktop': desktop,
                            'geometry': {'x': geometry_x, 'y': geometry_y, 'width': geometry_width, 'height': geometry_height},
                            'title': title
                        }

                        if 0 <= desktop <= 10:
                            parsed_window_list.append(window_data)

                        if window_id == active_window_id:
                            if 0 <= desktop <= 10:
                                parsed_active_window = window_data
                            else:
                                parsed_active_window = "N/A"
                    except ValueError:
                        continue # Skip malformed lines

        # Get default applications
        default_apps_cmd = '''for mime in text/html x-scheme-handler/mailto text/calendar audio/mpeg video/mp4 image/jpeg; do
                               echo "$mime: $(xdg-mime query default $mime)"
                           done'''
        default_apps_result = subprocess.run(default_apps_cmd, shell=True, capture_output=True, text=True)

        # Get system information
        uname_result = subprocess.run(['uname', '-a'], capture_output=True, text=True, check=True)
        lscpu_result = subprocess.run(['lscpu'], capture_output=True, text=True, check=True)
        free_result = subprocess.run(['free', '-h'], capture_output=True, text=True, check=True)

        # Parse default_applications
        parsed_default_apps = []
        for line in default_apps_result.stdout.strip().split('\n'):
            if ': ' in line:
                mime, app = line.split(': ', 1)
                parsed_default_apps.append({'mime_type': mime, 'application': app})

        return {
            'success': True,
            'window_list': parsed_window_list,
            'active_window': parsed_active_window,
            'default_applications': parsed_default_apps,
            'system_info': {
                'uname': uname_result.stdout.strip(),
                'lscpu': "\n".join(lscpu_result.stdout.strip().split('\n')[:20]),
                'free': free_result.stdout.strip()
            }
        }
    except subprocess.CalledProcessError as e:
        return {'error': f"Command failed: {e.cmd} - {e.stderr.strip()}"}, 500
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/changewmctrlinfo', methods=['POST'])
def change_wmctrl_info():
    try:
        data = request.get_json()
        window_id = data.get('id')

        if not window_id:
            return {'error': 'id is required'}, 400

        if not isinstance(window_id, str) or not window_id.startswith('0x') or not len(window_id) >= 3:
            return {'error': 'Invalid id format. Must be a hexadecimal string starting with 0x'}, 400

        try:
            int(window_id[2:], 16)
        except ValueError:
            return {'error': 'Invalid hexadecimal window_id'}, 400

        subprocess.run(['wmctrl', '-i', '-a', window_id], check=True)
        return {'success': True, 'window_id': window_id}
    except subprocess.CalledProcessError as e:
        return {'error': f"wmctrl command failed: {str(e)}"}, 500
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/click', methods=['POST'])
def click():
    print("[/click] Endpoint hit!")
    try:
        data = request.get_json()
        print(f"[/click] Received data: {data}")
        x = data.get('x')
        y = data.get('y')
        button = data.get('button', 'left') # left, middle, right
        clicks = data.get('clicks', 1)
        interval = data.get('interval', 0.0)

        # Convert to appropriate types after getting from dictionary
        try:
            x = int(x)
            y = int(y)
        except (ValueError, TypeError):
            print("[/click] Error: x and y coordinates must be integers.")
            return {'error': 'x and y coordinates must be integers'}, 400
        if button not in ['left', 'middle', 'right']:
            print(f"[/click] Error: Invalid button: {button}")
            return {'error': 'Invalid button. Must be left, middle, or right'}, 400
        if not isinstance(clicks, int) or clicks < 1:
            print(f"[/click] Error: Invalid clicks: {clicks}")
            return {'error': 'Clicks must be a positive integer'}, 400

        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
        print(f"[/click] Clicked at {x},{y} with {button} button, {clicks} times.")
        return {'success': True, 'x': x, 'y': y, 'button': button, 'clicks': clicks}
    except Exception as e:
        print(f"[/click] Exception: {e}")
        return {'error': str(e)}, 500

@app.route('/')
def index():
    return {
        'message': 'Screenshot and Automation API',
        'endpoints': {
            '/screenshot': 'GET - Capture and return a screenshot (params: x, y, width, height)',
            '/moveto': 'GET - Move cursor to absolute position (params: x, y)',
            '/moverel': 'GET - Move cursor relative to current position (params: direction, pixels)',
            '/input': 'POST - Type text or send key combinations (body: {"type": "text|hotkey", "content": string|array, "interval": float})',
            '/scroll': 'GET - Scroll up or down (params: direction, clicks)',
            '/screenresolution': 'GET - Get screen resolution',
            '/wmctrlinfo': 'GET - Get wmctrl -lG output',
            '/changewmctrlinfo': 'POST - Change window focus',
            '/click': 'POST - Click at specific coordinates with optional button and clicks'
        }
    }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6969)