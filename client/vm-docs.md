# Screenshot and Automation API Documentation

This API provides endpoints for screen capture, mouse control, keyboard input, and scrolling functionality.

## Base URL

```
http://<your-ip>:6969
```

## Available Endpoints

### GET `/screenshot`
- Captures a screenshot of the entire screen
- Can capture a specific region by providing x, y, width, and height parameters
- Returns a PNG image

**Example Request:**
```
GET /screenshot?x=100&y=100&width=500&height=300
```

**Success Response:**
```
[PNG Image Data]
```

**Error Response:**
```json
{
    "error": "scrot failed: Command returned non-zero exit status 1"
}
```

### GET `/moveto`
- Moves the mouse cursor to specific x, y coordinates on the screen
- Example: Move to position (100, 200)

**Example Request:**
```
GET /moveto?x=100&y=200
```

**Success Response:**
```json
{
    "success": true,
    "position": {
        "x": 100,
        "y": 200
    }
}
```

**Error Response:**
```json
{
    "error": "x and y coordinates are required"
}
```

### GET `/moverel`
- Moves the mouse cursor relative to its current position
- Supports directions: up, down, left, right, upleft, upright, downleft, downright
- Can specify number of pixels to move

**Example Request:**
```
GET /moverel?direction=up&pixels=20
```

**Success Response:**
```json
{
    "success": true,
    "position": {
        "x": 500,
        "y": 300
    }
}
```

**Error Response:**
```json
{
    "error": "Invalid direction"
}
```

### POST `/input`
- Handles keyboard input (typing and hotkeys)
- Can type text strings
- Can send keyboard shortcuts (like ctrl+c)
- Can press single keys (like F1)
- Configurable typing speed

**Example Requests:**

1. Type Text:
```json
POST /input
{
    "type": "text",
    "content": "Hello World",
    "interval": 0.1
}
```

2. Press Hotkey:
```json
POST /input
{
    "type": "hotkey",
    "content": ["ctrl", "c"]
}
```

3. Single Key:
```json
POST /input
{
    "type": "hotkey",
    "content": "f1"
}
```

**Success Response:**
```json
{
    "success": true,
    "type": "text",
    "typed": "Hello World"
}
```
or
```json
{
    "success": true,
    "type": "hotkey",
    "keys_pressed": ["ctrl", "c"]
}
```

**Error Response:**
```json
{
    "error": "content is required"
}
```

### GET `/scroll`
- Controls mouse wheel scrolling
- Scroll up or down
- Configurable number of scroll clicks

**Example Request:**
```
GET /scroll?direction=up&clicks=3
```

**Success Response:**
```json
{
    "success": true,
    "direction": "up",
    "clicks": 3
}
```

**Error Response:**
```json
{
    "error": "direction must be either \"up\" or \"down\""
}
```

## Quick Start

1. Install requirements:
```bash
pip install flask pyautogui pillow
sudo apt-get install scrot  # For Linux screenshots
```

2. Run the server:
```bash
python server.py
```

3. Replace `<your-ip>` with your actual IP address in the requests

## Security Note
PyAutoGUI has a failsafe feature - quickly move your mouse to any screen corner to abort operations. 