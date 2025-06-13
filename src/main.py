import types
from src.agent.llm import LLM
from src.agent.screen import VM
import os
from google.genai import types as genai_types
from jinja2 import Environment, FileSystemLoader
from PIL import Image
import io
import json
import time
from src.scan import OmniParser

def main():
    # Initialize VM
    vm_server_ip = os.getenv("VM_SERVER_IP", "192.168.1.64")
    vm_server_port = int(os.getenv("VM_SERVER_PORT", "6969"))
    vm = VM(vm_server_ip=vm_server_ip, vm_server_port=vm_server_port)

    # Initialize LLM
    LLM.initialize()
    
    # Initialize OmniParser
    omniparser = OmniParser()
    
    # Load Jinja2 environment
    env = Environment(loader=FileSystemLoader('template/'))
    
    # Get the vm_tools.j2 template
    template = env.get_template('tools/vm_tools.j2')

    screen_resolution = vm.get_screen_resolution()
    screen_width = screen_resolution.get("width")
    screen_height = screen_resolution.get("height")
   
    # Render the vm_tools_response_format macro
    vm_tools_prompt = template.module.vm_tools_response_format()

    prompt = "Open firefox"
   
    screenshot_bytes = vm.screenshot()
    pil_image = Image.open(io.BytesIO(screenshot_bytes))   
    
    success, ui_classification_with_pixels, ui_elements_json = omniparser.analyze_screenshot_data(screenshot_bytes, screen_width , screen_height, save_locally=True)
    ui_elements = json.loads(ui_elements_json)
    wmctrl_info = vm.get_wmctrl_info()

    print(f"UI Elements: {ui_elements}")
    print(f"UI Classification: {ui_classification_with_pixels}")
    exit()
    # Get screen resolution

    print(f"Screen Resolution: Width={screen_width}, Height={screen_height}")

    tasks = LLM.run(f"""
You are a computer use agent that breaks down tasks into granular, executable steps.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON array of step objects
2. Each step must be atomic and specific
3. Include ALL user interactions (clicks, keystrokes, confirmations)
4. Never assume default behaviors or skip prompts
5. Account for system prompts, password entries, confirmations, capcha, ect...
6. Use EXACT pixel coordinates from screenshots
7. Do not hallucinate actions or information that you are not sure about.

FORMAT: [{{"step": "description"}}, {{"step": "description"}}, ...]

EXAMPLE BREAKING DOWN "Install Firefox":
[
  {{"step": "open terminal application"}},
  {{"step": "type 'sudo apt update' and press Enter"}},
  {{"step": "enter system password when prompted"}},
  {{"step": "wait for update process to complete"}},
  {{"step": "type 'sudo apt install firefox' and press Enter"}},
  {{"step": "type 'y' when prompted to confirm installation"}},
  {{"step": "press Enter to confirm"}},
  {{"step": "wait for installation to complete"}},
  {{"step": "type 'firefox' to launch browser"}},
  {{"step": "press Enter"}}
]

This example shows the level of detail needed - think like this for EVERY task. Don't forget single interactions but don't overcomplicate things either.

RULES:
- Include every keystroke, click, and wait needed
- Specify exact text to type
- Include password prompts and confirmations
- Account for loading/processing time
- Be explicit about UI interactions
- No explanatory text outside JSON
- No assumptions about default settings
- Keep steps simple and direct - don't overthink

Current windows: {wmctrl_info}
Task to break down: {prompt}
""", prompt + " Here is the ui classification: " + ui_classification_with_pixels + " and the ui elements: " + json.dumps(ui_elements), force_json_output=True, image=pil_image)

    tasks = json.loads(tasks)

    print(tasks)
    
    for i, task in enumerate(tasks):
        print(task)
        print("AAAAAAAAAA")
        screenshot_bytes = vm.screenshot()
        pil_image = Image.open(io.BytesIO(screenshot_bytes))

        success, ui_classification_with_pixels, ui_elements_json = omniparser.analyze_screenshot_data(screenshot_bytes, screen_width, screen_height, save_locally=True)
        ui_elements = json.loads(ui_elements_json)
       
        # Get screen resolution again for the loop
        screen_resolution = vm.get_screen_resolution()
        screen_width = screen_resolution.get("width")
        screen_height = screen_resolution.get("height")

        print(f"Screen Resolution: Width={screen_width}, Height={screen_height}")

        # Get wmctrl info
        wmctrl_info = vm.get_wmctrl_info()

        previous_task = tasks[i-1] if i > 0 else "None"
        next_task = tasks[i+1] if i < len(tasks) - 1 else "None"

        full_prompt = f"""You are a computer use agent that executes actions using the provided tools. Your current task is: {task}.

CONTEXT:
- Previous task: {previous_task}
- Next task: {next_task}
- Current windows: {wmctrl_info}
- UI Elements: {json.dumps(ui_elements)}, {ui_classification_with_pixels}
- The main user prompt for context: {prompt}

EXECUTION STRATEGY:
1. ANALYZE FIRST: Before taking any action, examine the current screenshot and UI state
2. PLAN YOUR APPROACH: Consider the most efficient path to complete the task
3. EXECUTE STEP-BY-STEP: Take one action at a time and verify results
4. ADAPT AS NEEDED: If something doesn't work as expected, adjust your approach

CRITICAL EXECUTION RULES:
1. SLOW SYSTEM AWARENESS:
   - Use minimum 2-3 second sleeps between actions
   - Wait 5+ seconds after opening applications
   - Allow extra time for page loads and file operations

2. PRECISE INTERACTION:
   - Use EXACT pixel coordinates from screenshots
   - Double-click desktop icons to open applications
   - Single-click for menu items and buttons
   - Verify element visibility before clicking

3. CONTEXT AWARENESS:
   - Check window focus before interacting
   - Handle popups, dialogs, and notifications immediately
   - Consider overlapping windows and scrollbars
   - Maintain awareness of current application state

4. ERROR HANDLING:
   - If an element isn't found, take a new screenshot
   - If a click doesn't work, try slightly different coordinates
   - If an application doesn't respond, wait longer before retrying
   - Always verify your actions succeeded before proceeding

5. EFFICIENT TOOL USAGE:
   - Stack multiple VM tools for complex sequences
   - Use keyboard shortcuts when faster than mouse navigation
   - Take screenshots frequently to track progress
   - Combine actions when logically connected

PROBLEM-SOLVING APPROACH:
- If task seems impossible, break it into smaller sub-tasks
- If UI elements are unclear, take a fresh screenshot
- If applications are unresponsive, consider restarting them
- If permissions are needed, handle authentication prompts
- If files/folders don't exist, create them as needed

QUALITY CHECKS:
- Verify each action completed successfully
- Confirm you're in the right application/window
- Check that text was typed correctly
- Ensure file operations completed properly
- Validate final result matches task requirements
- Do not hallucinate actions or information that you are not sure about.

COMMUNICATION:
- Explain your reasoning for each action
- Describe what you observe in screenshots
- Report any unexpected behavior or errors
- Confirm task completion with evidence

Available tools: {vm_tools_prompt}

REMEMBER: You have access to the complete desktop environment. Use visual cues from screenshots to navigate accurately. Take your time and be methodical - precision is more important than speed."""
        response = LLM.run(full_prompt, json.dumps(task), force_json_output=True, image=pil_image)
        print(response)
    
    # Parse the JSON response and execute VM operations
        response_json = json.loads(response)
        operations = response_json.get("operations", [])

        for op in operations:
            op_type = op.get("type")
            if op_type == "action":
                action_name = op.get("action_name")
                parameters = op.get("parameters", {})
                print(f"DEBUG: Raw action_name: '{action_name}', Stripped action_name: '{action_name.strip()}'")
                if hasattr(vm, action_name):
                    action_func = getattr(vm, action_name)
                    if action_name.strip() == "input":
                        input_type = parameters.pop("type")
                        content = parameters.pop("content")
                        action_func(input_type, content, **parameters)
                    else:
                        action_func(**parameters)
                print(f"Executed VM action: {action_name} with parameters {parameters}")
            elif op_type == "sleep":
                duration_ms = op.get("duration_ms")
                if duration_ms is not None:
                    time.sleep(duration_ms / 1000.0) # Convert ms to seconds
                    print(f"Slept for {duration_ms} ms")
            else:
                print(f"Unknown operation type: {op_type}")

if __name__ == "__main__":
    main()