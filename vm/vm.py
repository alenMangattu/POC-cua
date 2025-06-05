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
            return {'success': True, 'type': 'text', 'typed': content}
 
        elif input_type == 'hotkey':
            # Handle hotkey combinations
            if isinstance(content, list):
                pyautogui.hotkey(*content)
                return {'success': True, 'type': 'hotkey', 'keys_pressed': content}
            else:
                # Single key press
                pyautogui.press(content)
                return {'success': True, 'type': 'hotkey', 'key_pressed': content}
 
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
        else:
            pyautogui.scroll(-clicks)
 
        return {'success': True, 'direction': direction, 'clicks': clicks}
    except Exception as e:
        return {'error': str(e)}, 500
 
@app.route('/wmctrlinfo', methods=['GET'])
def get_wmctrl_info():
    try:
        # Get general window info
        wmctrl_result = subprocess.run(['wmctrl', '-lG'], capture_output=True, text=True, check=True)
        
        # Get active window info
        active_window_cmd = "xdotool getactivewindow"
        active_window_id_raw = subprocess.run(active_window_cmd, shell=True, capture_output=True, text=True, check=True).stdout.strip()
        active_window_id = f"0x{int(active_window_id_raw, 10):08x}" if active_window_id_raw else ""
        
        active_window_info = ""
        if active_window_id:
            active_window_lookup_cmd = f"wmctrl -lG | grep {active_window_id}"
            active_window_lookup_result = subprocess.run(active_window_lookup_cmd, shell=True, capture_output=True, text=True)
            active_window_info = active_window_lookup_result.stdout.strip()

        # Get default applications
        default_apps_cmd = '''for mime in text/html x-scheme-handler/mailto text/calendar audio/mpeg video/mp4 image/jpeg; do
                               echo "$mime: $(xdg-mime query default $mime)"
                           done'''
        default_apps_result = subprocess.run(default_apps_cmd, shell=True, capture_output=True, text=True)

        # Get system information
        uname_result = subprocess.run(['uname', '-a'], capture_output=True, text=True, check=True)
        lscpu_result = subprocess.run(['lscpu'], capture_output=True, text=True, check=True)
        free_result = subprocess.run(['free', '-h'], capture_output=True, text=True, check=True)
        
        # Parse window_list
        parsed_window_list = []
        for line in wmctrl_result.stdout.strip().split('\n'):
            if line:
                parts = line.split(None, 8)  # Split by whitespace, max 8 splits
                if len(parts) >= 8:
                    try:
                        window_id = parts[0]
                        desktop = int(parts[1])
                        geometry_x = int(parts[2])
                        geometry_y = int(parts[3])
                        geometry_width = int(parts[4])
                        geometry_height = int(parts[5])
                        # hostname = parts[6] # Removed as per user request
                        title = parts[7]
                        if 0 <= desktop <= 10:
                            parsed_window_list.append({
                                'id': window_id,
                                'desktop': desktop,
                                'geometry': {'x': geometry_x, 'y': geometry_y, 'width': geometry_width, 'height': geometry_height},
                                # 'hostname': hostname, # Removed as per user request
                                'title': title
                            })
                    except ValueError:
                        # Handle cases where parsing fails for a line
                        continue
        
        # Parse active_window
        parsed_active_window = {}
        if active_window_info:
            parts = active_window_info.split(None, 8)
            if len(parts) >= 8:
                try:
                    window_id = parts[0]
                    desktop = int(parts[1])
                    geometry_x = int(parts[2])
                    geometry_y = int(parts[3])
                    geometry_width = int(parts[4])
                    geometry_height = int(parts[5])
                    # hostname = parts[6] # Removed as per user request
                    title = parts[7]
                    parsed_active_window = {
                        'id': window_id,
                        'desktop': desktop,
                        'geometry': {'x': geometry_x, 'y': geometry_y, 'width': geometry_width, 'height': geometry_height},
                        # 'hostname': hostname, # Removed as per user request
                        'title': title
                    }
                except ValueError:
                    pass # Keep as empty if parsing fails

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
        window_id = data.get('window_id')

        if not window_id:
            return {'error': 'window_id is required'}, 400

        if not isinstance(window_id, str) or not window_id.startswith('0x') or not len(window_id) >= 3:
            return {'error': 'Invalid window_id format. Must be a hexadecimal string starting with 0x'}, 400

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
            '/wmctrlinfo': 'GET - Get wmctrl -lG output',
            '/changewmctrlinfo': 'POST - Change window focus'
        }
    }
 
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=6969)