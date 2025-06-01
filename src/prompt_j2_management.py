from jinja2 import Environment, FileSystemLoader
import os

# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(__file__), '../templates')
env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)

def analyse_genesis_classification(context=None):
    if context is None:
        context = {} # Ensure context is always a dict
    
    template = env.get_template("system_gensis_classification.j2")
    
    # Ensure 'scan' and 'ui_screen' have defaults if not in context for rendering
    # This makes the template rendering more robust.
    scan_value = context.get("scan", False)
    ui_screen_value = context.get("ui_screen", [])
    
    return template.render(
        scan=scan_value,
        ui_screen=ui_screen_value
    )
    
def get_vision_model_prompt():
    template = env.get_template("tools/vision_model.j2")
    return template.render()