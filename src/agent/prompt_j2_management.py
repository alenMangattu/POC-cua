from jinja2 import Environment, FileSystemLoader
import os
from src.utils import task_to_json_dict # Import the helper function from utils.py

# Setup Jinja2 environment
template_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')), 'template')
env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)

def local_get_wmctrl_info(wmctrlinfo):
    if wmctrlinfo is None:
        raise ValueError("wmctrlinfo is required")
    return wmctrlinfo

def analyse_genesis_classification(context=None, wmctrlinfo=None):
    if context is None:
        context = {} # Ensure context is always a dict
    
    # Use the passed wmctrlinfo directly
    wmctrlinfo_data = local_get_wmctrl_info(wmctrlinfo)
    template = env.get_template("system_gensis_classification.j2")
    
    scan_value = context.get("scan", False)
    ui_screen_value = context.get("ui_screen", [])

    return template.render(
        scan=scan_value,
        ui_screen=ui_screen_value,
        wmctrlinfo=wmctrlinfo_data
    )
   
def get_vision_model_prompt(context=None):
    if context is None:
        context = {} # Ensure context is always a dict
    template = env.get_template("tools/vision_model.j2")
    return template.render(
        scan=context.get("scan", False),
        ui_screen=context.get("ui_screen", [])
    )

def get_system_l1_prompt(context=None):
    if context is None:
        context = {} # Ensure context is always a dict
    template = env.get_template("system_l1_sequence_to_action.j2")
    return template.render(
        wmctrlinfo=context.get("wmctrlinfo", {}),
        task_step=context.get("task_step", {}),
        prev_l1_actions=context.get("prev_l1_actions", None),
        next_l2_steps=context.get("next_l2_steps", [])
    )

def get_system_l2_prompt(context=None):
    if context is None:
        context = {} # Ensure context is always a dict
        
    
    template = env.get_template("system_l2_task_to_sequence.j2")
    return template.render(
        wmctrlinfo=context.get("wmctrlinfo", {}),
        htn=False # Explicitly set htn to False for L2 tasks
    )

def get_planner_prompt(context=None):
    if context is None:
        context = {}
        
    template = env.get_template("planner.j2")
    return template.render(
        wmctrlinfo=context.get("wmctrlinfo", {}),
        htn=False # Explicitly set htn to False for L2 tasks
    )

def get_executer_prompt(context=None):
    if context is None:
        context = {}
    template = env.get_template("executer.j2")
    return template.render(
        wmctrlinfo=context.get("wmctrlinfo", {}),
        htn=False # Explicitly set htn to False for L2 tasks
    )

def get_implementation_planner_prompt(context=None):
    if context is None:
        context = {}
    template = env.get_template("implementation_planner.j2")
    task_data = context.get("task", {})
    # Ensure the task object is JSON-serializable before passing to the template
    processed_task = task_to_json_dict(task_data)

    return template.render(
        wmctrlinfo=context.get("wmctrlinfo", {}),
        task=processed_task,
        available_outputs=context.get("available_outputs", {}),
        current_screen_state=context.get("current_screen_state", None)
    )