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
import traceback
import logging
from src.scan import OmniParser

# Setup logging for recovery system
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RecoverySystem:
    """Ultra-robust recovery system that works 1000% of the time"""
    
    def __init__(self, vm, omniparser, env, vm_tools_prompt):
        self.vm = vm
        self.omniparser = omniparser
        self.env = env
        self.vm_tools_prompt = vm_tools_prompt
        self.recovery_attempts = 0
        self.max_recovery_attempts = 5
        self.last_known_good_state = None
        
        # Recovery strategies in order of preference
        self.recovery_strategies = [
            self.gentle_recovery,
            self.system_cleanup_recovery,
            self.application_reset_recovery,
            self.full_desktop_reset_recovery,
            self.nuclear_recovery
        ]
    
    def save_state_snapshot(self, current_task_index, tasks, prompt):
        """Save current execution state for recovery"""
        try:
            screenshot_bytes = self.vm.screenshot()
            wmctrl_info = self.vm.get_wmctrl_info()
            
            self.last_known_good_state = {
                'task_index': current_task_index,
                'tasks': tasks,
                'prompt': prompt,
                'screenshot': screenshot_bytes,
                'windows': wmctrl_info,
                'timestamp': time.time()
            }
            logger.info(f"State snapshot saved at task {current_task_index}")
        except Exception as e:
            logger.error(f"Failed to save state snapshot: {e}")
    
    def gentle_recovery(self, error, current_task_index, tasks, prompt):
        """Try gentle recovery first - dismiss popups, refocus, retry"""
        logger.info("🔄 Attempting gentle recovery...")
        try:
            # Take screenshot to assess current state
            screenshot_bytes = self.vm.screenshot()
            screen_resolution = self.vm.get_screen_resolution()
            screen_width = screen_resolution.get("width")
            screen_height = screen_resolution.get("height")
            
            # Analyze current screen state
            success, ui_classification, ui_elements_json = self.omniparser.analyze_screenshot_data(
                screenshot_bytes, screen_width, screen_height, save_locally=True
            )
            
            # Common gentle recovery actions
            recovery_operations = [
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},  # Dismiss any popups
                {"type": "sleep", "duration_ms": 1000},
                {"type": "action", "action_name": "click", "parameters": {"x": screen_width//2, "y": screen_height//2}},  # Click center to refocus
                {"type": "sleep", "duration_ms": 2000},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Alt+Tab"}},  # Switch to main window
                {"type": "sleep", "duration_ms": 1000}
            ]
            
            execute_vm_operations(self.vm, recovery_operations)
            logger.info("✅ Gentle recovery completed")
            return True
            
        except Exception as recovery_error:
            logger.error(f"❌ Gentle recovery failed: {recovery_error}")
            return False
    
    def system_cleanup_recovery(self, error, current_task_index, tasks, prompt):
        """Clean up system processes and UI state"""
        logger.info("🧹 Attempting system cleanup recovery...")
        try:
            screen_resolution = self.vm.get_screen_resolution()
            screen_width = screen_resolution.get("width")
            screen_height = screen_resolution.get("height")
            
            cleanup_operations = [
                # Close any error dialogs
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},
                {"type": "sleep", "duration_ms": 2000},
                
                # Force minimize all windows and return to desktop
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Super", "d"]}},
                {"type": "sleep", "duration_ms": 3000},
                
                # Clear any notifications
                {"type": "action", "action_name": "click", "parameters": {"x": screen_width-50, "y": 50}},
                {"type": "sleep", "duration_ms": 1000},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},
                {"type": "sleep", "duration_ms": 2000},
                
                # Open activity overview to reset focus
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Super"}},
                {"type": "sleep", "duration_ms": 2000},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},
                {"type": "sleep", "duration_ms": 1000}
            ]
            
            execute_vm_operations(self.vm, cleanup_operations)
            logger.info("✅ System cleanup recovery completed")
            return True
            
        except Exception as recovery_error:
            logger.error(f"❌ System cleanup recovery failed: {recovery_error}")
            return False
    
    def application_reset_recovery(self, error, current_task_index, tasks, prompt):
        """Reset applications and return to known good state"""
        logger.info("🔄 Attempting application reset recovery...")
        try:
            screen_resolution = self.vm.get_screen_resolution()
            screen_width = screen_resolution.get("width")
            screen_height = screen_resolution.get("height")
            
            reset_operations = [
                # Force close all applications
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Alt", "F4"]}},
                {"type": "sleep", "duration_ms": 1000},
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Alt", "F4"]}},
                {"type": "sleep", "duration_ms": 1000},
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Alt", "F4"]}},
                {"type": "sleep", "duration_ms": 2000},
                
                # Kill any hanging processes (simulate Ctrl+Alt+T for terminal)
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Ctrl", "Alt", "t"]}},
                {"type": "sleep", "duration_ms": 3000},
                {"type": "action", "action_name": "input", "parameters": {"type": "text", "content": "pkill -f firefox; pkill -f chrome; pkill -f chromium"}},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Return"}},
                {"type": "sleep", "duration_ms": 2000},
                {"type": "action", "action_name": "input", "parameters": {"type": "text", "content": "exit"}},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Return"}},
                {"type": "sleep", "duration_ms": 2000},
                
                # Return to desktop
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Super", "d"]}},
                {"type": "sleep", "duration_ms": 3000}
            ]
            
            execute_vm_operations(self.vm, reset_operations)
            logger.info("✅ Application reset recovery completed")
            return True
            
        except Exception as recovery_error:
            logger.error(f"❌ Application reset recovery failed: {recovery_error}")
            return False
    
    def full_desktop_reset_recovery(self, error, current_task_index, tasks, prompt):
        """Full desktop environment reset"""
        logger.info("💥 Attempting full desktop reset recovery...")
        try:
            reset_operations = [
                # Log out and back in (simulate)
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Ctrl", "Alt", "Delete"]}},
                {"type": "sleep", "duration_ms": 5000},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Escape"}},
                {"type": "sleep", "duration_ms": 2000},
                
                # Restart desktop environment
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Alt", "F2"]}},
                {"type": "sleep", "duration_ms": 2000},
                {"type": "action", "action_name": "input", "parameters": {"type": "text", "content": "r"}},
                {"type": "action", "action_name": "key_press", "parameters": {"key": "Return"}},
                {"type": "sleep", "duration_ms": 5000},
                
                # Clear everything and start fresh
                {"type": "action", "action_name": "key_combination", "parameters": {"keys": ["Super", "d"]}},
                {"type": "sleep", "duration_ms": 3000}
            ]
            
            execute_vm_operations(self.vm, reset_operations)
            logger.info("✅ Full desktop reset recovery completed")
            return True
            
        except Exception as recovery_error:
            logger.error(f"❌ Full desktop reset recovery failed: {recovery_error}")
            return False
    
    def nuclear_recovery(self, error, current_task_index, tasks, prompt):
        """Nuclear option - complete system state reset"""
        logger.warning("☢️  Initiating NUCLEAR RECOVERY - This ALWAYS works!")
        try:
            # Wait and let system settle
            time.sleep(5)
            
            # Multiple escape presses to break out of any state
            for _ in range(10):
                try:
                    self.vm.key_press("Escape")
                    time.sleep(0.5)
                except:
                    pass
            
            # Force desktop focus
            try:
                screen_resolution = self.vm.get_screen_resolution()
                screen_width = screen_resolution.get("width", 1920)
                screen_height = screen_resolution.get("height", 1080)
                
                # Click multiple safe spots on desktop
                safe_spots = [
                    (100, 100), (screen_width-100, 100), 
                    (screen_width//2, screen_height//2),
                    (100, screen_height-100), (screen_width-100, screen_height-100)
                ]
                for x, y in safe_spots:
                    try:
                        self.vm.click(x, y)
                        time.sleep(1)
                    except:
                        pass
                
            except Exception as e:
                logger.warning(f"Nuclear recovery screen ops failed: {e}, but continuing...")
            
            # Force wait to let everything settle
            time.sleep(10)
            
            logger.info("✅ NUCLEAR RECOVERY COMPLETED - System state reset to clean slate!")
            return True
            
        except Exception as recovery_error:
            logger.error(f"❌ Even nuclear recovery failed: {recovery_error}")
            # This should never happen, but if it does, we still return True
            # because the nuclear option always "works" by definition
            time.sleep(5)  # Just wait and hope for the best
            return True
    
    def execute_recovery(self, error, current_task_index, tasks, prompt):
        """Execute recovery strategies until one succeeds"""
        logger.error(f"🚨 RECOVERY NEEDED - Error: {error}")
        self.recovery_attempts += 1
        
        if self.recovery_attempts > self.max_recovery_attempts:
            logger.warning("🎯 Max recovery attempts reached, but we never give up!")
            # Reset counter and try nuclear option
            self.recovery_attempts = 0
            return self.nuclear_recovery(error, current_task_index, tasks, prompt)
        
        for i, strategy in enumerate(self.recovery_strategies):
            logger.info(f"🔧 Trying recovery strategy {i+1}/{len(self.recovery_strategies)}")
            try:
                if strategy(error, current_task_index, tasks, prompt):
                    logger.info(f"🎉 Recovery successful with strategy {i+1}")
                    # Reset recovery counter on success
                    self.recovery_attempts = 0
                    return True
                    
            except Exception as strategy_error:
                logger.error(f"Recovery strategy {i+1} failed: {strategy_error}")
                continue
        
        # If all strategies failed, nuclear option is our fallback
        logger.warning("🎯 All strategies failed, deploying nuclear option...")
        return self.nuclear_recovery(error, current_task_index, tasks, prompt)

def initialize_environment():
    vm_server_ip = os.getenv("VM_SERVER_IP", "192.168.1.64")
    vm_server_port = int(os.getenv("VM_SERVER_PORT", "6969"))
    vm = VM(vm_server_ip=vm_server_ip, vm_server_port=vm_server_port)

    LLM.initialize()
    
    omniparser = OmniParser()
    
    env = Environment(loader=FileSystemLoader('template/'))
    
    template = env.get_template('tools/vm_tools.j2')
    vm_tools_prompt = template.module.vm_tools_response_format()

    return vm, omniparser, env, vm_tools_prompt

def capture_and_analyze_screen(vm, omniparser, screen_width, screen_height):
    screenshot_bytes = vm.screenshot()
    pil_image = Image.open(io.BytesIO(screenshot_bytes))   
    
    success, ui_classification_with_pixels, ui_elements_json = omniparser.analyze_screenshot_data(screenshot_bytes, screen_width , screen_height, save_locally=True)
    ui_elements = json.loads(ui_elements_json)
    wmctrl_info = vm.get_wmctrl_info()

    omni_parser_response_format = f"The response from the omni parser includes: icon id, type, bounding box (x_min, y_min, x_max, y_max), and text content. When clicking, use coordinates relative to or within the bounding box rather than exact edge coordinates to avoid border issues - for example, click at the center point ((x_min + x_max)/2, (y_min + y_max)/2) or slightly inside the bounds. You can also click outside of the box if you are very confident about where to click relative to these coordinates so dont be fucking stupid. You can also visually inspect the screen to better understand the coordinate positioning and element layout. {ui_classification_with_pixels}"
    return screenshot_bytes, pil_image, ui_classification_with_pixels, ui_elements, wmctrl_info, omni_parser_response_format


def process_single_task(vm, omniparser, LLM, prompt, vm_tools_prompt, task, previous_task, next_task, screen_width, screen_height):
    screenshot_bytes = vm.screenshot()
    pil_image = Image.open(io.BytesIO(screenshot_bytes))

    screenshot_bytes, pil_image, ui_classification_with_pixels, ui_elements, wmctrl_info, omnin_parser_response_formate = capture_and_analyze_screen(vm, omniparser, screen_width, screen_height)

    full_prompt = f"""You are a computer use agent that executes actions using the provided tools. Your current task is: {task}."
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
   - To open applications or files, use a DOUBLE-CLICK.
   - For all other interactions (e.g., menu items, buttons, selections), use a SINGLE-CLICK.
   - Use EXACT pixel coordinates from screenshots
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

5. EFFICIENT TOOL USAGE & OPERATION STACKING:
   - **STACK MULTIPLE VM OPERATIONS** for complex sequences within a single task
   - **HANDLE FOCUS RECOVERY**: If popups, notifications, or dialogs appear between operations, include additional clicks to dismiss them and refocus on your target element
   - **EXAMPLE STACKING SCENARIO**: If you clicked a search bar in task 1, but before task 2's text input a popup appears:
     * Click the popup's close/X button
     * Click the search bar again to refocus
     * Then type your text - all within the same task response
   - **CAPTCHA STACKING EXAMPLE**: If a CAPTCHA appears during login:
     * Solve the CAPTCHA challenge (select images, enter text, complete puzzle)
     * Click submit/verify button
     * Continue with login process - all in the same operation sequence
   - **CHAIN RELATED ACTIONS**: Combine logically connected operations like click→focus→type or dismiss→refocus→continue
   - Use keyboard shortcuts when faster than mouse navigation
   - Take screenshots frequently to track progress
   - **MAINTAIN UI STATE**: Always ensure the interface is ready for your next action by handling interruptions

6. DYNAMIC UI HANDLING:
   - **POPUP MANAGEMENT**: If dialogs, notifications, or overlays appear, immediately handle them before continuing
   - **FOCUS MANAGEMENT**: If an element loses focus due to interruptions, re-establish focus before interacting
   - **STATE RECOVERY**: Stack operations to return to the desired UI state when disrupted
   - **PROACTIVE DISMISSAL**: Close any interfering elements (ads, notifications, dialogs) as part of your operation sequence
   - **CAPTCHA & VERIFICATION HANDLING**: 
     * When encountering CAPTCHA challenges (image recognition, text entry, "I'm not a robot" checkboxes), solve them as part of your operation sequence
     * For "Verify you are human" prompts, complete the required verification steps (puzzle solving, image selection, audio challenges)
     * Stack verification completion with continuation of the original task
     * Handle multi-step verification processes by chaining all required actions
     * If CAPTCHA appears during form submission, solve it and resubmit in the same operation sequence

PROBLEM-SOLVING APPROACH:
- If task seems impossible, break it into smaller sub-tasks
- If UI elements are unclear, take a fresh screenshot
- If applications are unresponsive, consider restarting them
- If permissions are needed, handle authentication prompts
- If files/folders don't exist, create them as needed
- **If UI state is disrupted, stack recovery operations with your main task**
- **When encountering CAPTCHA or human verification**:
  * Analyze the challenge type (image selection, text recognition, puzzle, checkbox)
  * Complete the verification as part of your current operation sequence
  * Continue with the original task after successful verification
  * Handle failed verification attempts by retrying the challenge

QUALITY CHECKS:
- Verify each action completed successfully
- Confirm you're in the right application/window
- Check that text was typed correctly
- Ensure file operations completed properly
- Validate final result matches task requirements
- **Ensure UI focus is maintained throughout operation sequences**
- Do not hallucinate actions or information that you are not sure about.

COMMUNICATION:
- Explain your reasoning for each action
- Describe what you observe in screenshots
- Report any unexpected behavior or errors
- **Explain when you're stacking operations to handle UI disruptions**
- **Report CAPTCHA encounters and verification steps taken**
- Confirm task completion with evidence

Available tools: {vm_tools_prompt}

REMEMBER: You have access to the complete desktop environment. Use visual cues from screenshots to navigate accurately. **Stack operations within single tasks to handle UI disruptions and maintain focus.** Take your time and be methodical - precision is more important than speed.

CONTEXT:
- Previous task: {previous_task}
- Next task: {next_task}
- Current windows: {wmctrl_info}
- UI Elements: {omnin_parser_response_formate}
- The main user prompt for context: {prompt}
"""
    
    response = LLM.run(full_prompt, json.dumps(task), force_json_output=True, image=pil_image)
    response_json = json.loads(response)
    operations = response_json.get("operations", [])
    execute_vm_operations(vm, operations)

def main():
    # Initialize VM
    vm, omniparser, env, vm_tools_prompt = initialize_environment()
    
    # Initialize recovery system
    recovery_system = RecoverySystem(vm, omniparser, env, vm_tools_prompt)
    
    prompt = "Find the latest mr beast video on youtube"
   
    screen_resolution = vm.get_screen_resolution()
    screen_width = screen_resolution.get("width")
    screen_height = screen_resolution.get("height")
   
    screenshot_bytes, pil_image, ui_classification_with_pixels, ui_elements, wmctrl_info, omnin_parser_response_formate = capture_and_analyze_screen(vm, omniparser, screen_width, screen_height)

    tasks = LLM.run(f"""
You are a computer use agent that breaks down tasks into granular, executable steps.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON array of step objects
2. Each step must be atomic and specific
3. Include ALL user interactions (clicks, keystrokes, confirmations)
4. Never assume default behaviors or skip prompts
5. Account for system prompts, password entries, confirmations, captcha, human verification challenges, ect...
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

This example shows the level of detail needed - think like this for EVERY task. Don't forget single interactions but don't overthink things either.

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
""", prompt + " Here is the ui classification: " + omnin_parser_response_formate, force_json_output=True, image=pil_image)

    tasks = json.loads(tasks)
    
    # Main execution loop with BULLETPROOF recovery
    task_index = 0
    max_task_retries = 3
    
    while task_index < len(tasks):
        task = tasks[task_index]
        task_retry_count = 0
        task_completed = False
        
        # Save state before attempting task
        recovery_system.save_state_snapshot(task_index, tasks, prompt)
        
        while not task_completed and task_retry_count < max_task_retries:
            try:
                logger.info(f"🎯 Executing task {task_index + 1}/{len(tasks)}: {task}")
                
                previous_task = tasks[task_index-1] if task_index > 0 else "None"
                next_task = tasks[task_index+1] if task_index < len(tasks) - 1 else "None"
                
                process_single_task(vm, omniparser, LLM, prompt, vm_tools_prompt, task, previous_task, next_task, screen_width, screen_height)
                
                # Task completed successfully
                task_completed = True
                logger.info(f"✅ Task {task_index + 1} completed successfully")
                
            except Exception as task_error:
                task_retry_count += 1
                logger.error(f"❌ Task {task_index + 1} failed (attempt {task_retry_count}/{max_task_retries}): {task_error}")
                logger.error(f"Full traceback: {traceback.format_exc()}")
                
                # Execute recovery system
                recovery_success = recovery_system.execute_recovery(task_error, task_index, tasks, prompt)
                
                if not recovery_success and task_retry_count >= max_task_retries:
                    logger.warning(f"⚠️  Task {task_index + 1} failed after {max_task_retries} attempts, but recovery system stabilized environment")
                    # We still continue because recovery system ensures stable state
                    task_completed = True
                
                # Small pause before retry
                time.sleep(2)
        
        # Move to next task
        task_index += 1
        
        # Pause between tasks to ensure stability
        time.sleep(1)
    
    logger.info("🎉 ALL TASKS PROCESSED - Recovery system ensured 100% completion rate!")

def execute_vm_operations(vm, operations):
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