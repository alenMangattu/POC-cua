from jinja2 import Environment, FileSystemLoader
import os
from .screen import VM

# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(__file__), '../templates')
env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)

def local_get_wmctrl_info(vm_instance: VM):
    if vm_instance is None:
        raise ValueError("VM instance is required")
    return vm_instance.get_wmctrl_info()

def analyse_genesis_classification(context=None, vm_instance: VM = None):
    if context is None:
        context = {} # Ensure context is always a dict
    
    wmctrlinfo = local_get_wmctrl_info(vm_instance)
    template = env.get_template("system_gensis_classification.j2")
    
    scan_value = context.get("scan", False)
    ui_screen_value = context.get("ui_screen", [])

    return template.render(
        scan=scan_value,
        ui_screen=ui_screen_value,
        wmctrlinfo=wmctrlinfo
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
