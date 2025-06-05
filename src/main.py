from .llm import LLM
from jinja2 import Template, Environment, FileSystemLoader
from google.genai import types
import json
import os
from dotenv import load_dotenv

from .screen import VM
from .prompt_j2_management import analyse_genesis_classification
from .calling_tools.classificaition_parser import parse_llm_classification_output
from .calling_tools.images.scan import OmniParser
from .calling_tools.images.vision_model import VisionModel

def scan_inital_prompt(user_input: str, context: dict = None) -> dict:
    prompt_sys_genesis_classification = analyse_genesis_classification(context)
    llm_response = LLM.run(
        prompt_sys_genesis_classification,
        user_input,
        config=types.GenerateContentConfig(
            temperature=1,
            candidate_count=1,
            max_output_tokens=8192,
            top_p=0.95,
        )
    )
    return parse_llm_classification_output(llm_response)

prompt = input("Enter your prompt: ")
# prompt = "fix this error on my screen"
response = scan_inital_prompt(prompt, None)
print("Initial classification response:")
print(json.dumps(response, indent=4))
vm = VM("192.168.1.64", 6969)

load_dotenv()
omniparser_url = os.getenv("OMNI_URL")
omniParser = OmniParser(omniparser_url)
visionModel = VisionModel()

analysis_result_dict = {}

if response.get("classification") == "SCAN":
    method = response.get("method")
    vision_model_query = response.get("vision_model_query")

    # print(f"\nProcessing SCAN classification with method: {method}")

    try:
        screenshot_bytes = vm.screenshot()
        print(f"Screenshot captured successfully ({len(screenshot_bytes)} bytes).")
    except Exception as e:
        print(f"✗ Failed to capture screenshot: {e}")
        analysis_result_dict = {"error": "Screenshot capture failed", "details": str(e)}
        print("\nFinal analysis result:")
        print(json.dumps(analysis_result_dict, indent=4))
        exit()

    omniParser = OmniParser(omniparser_url)
    visionModel = VisionModel()

    analysis_result_dict = {}

    if method == "OmniParser":
        print("Analyzing with Omni Parser...")
        omni_success, omni_ui_class, omni_ui_elements = omniParser.analyze_screenshot_data(screenshot_bytes, save_locally=False)
        analysis_result_dict["omni_parser"] = {
            "success": omni_success,
            "ui_classification": omni_ui_class,
            "ui_elements": omni_ui_elements
        }
        
        # analysis_result_dict["omni_parser"] = "blank ubuntu screen"
        if not omni_success:
            print("OmniParser analysis did not report success.")

    elif method == "VisionModel":
        print("Analyzing with Vision Model...")
        vision_output = visionModel.analyze(screenshot_bytes, vision_model_query)
        analysis_result_dict["vision_model"] = vision_output

    elif method == "OmniParserVisionModel":
        print("Analyzing with Omni Parser...")
        omni_success, omni_ui_class, omni_ui_elements = omniParser.analyze_screenshot_data(screenshot_bytes, save_locally=False)
        analysis_result_dict["omni_parser"] = {
            "success": omni_success,
            "ui_classification": omni_ui_class,
            "ui_elements": omni_ui_elements
        }

        if not omni_success:
            print("OmniParser analysis did not report success. Vision Model analysis will still be attempted if a query is available.")
        
        if vision_model_query:
            print("Analyzing with Vision Model...")
            vision_output = visionModel.analyze(screenshot_bytes, vision_model_query)
            analysis_result_dict["vision_model"] = vision_output
        else:
            print("Warning: No vision_model_query provided for 'Omni Parser + Vision Model' method, though it was expected. Skipping Vision Model analysis.")
            analysis_result_dict["vision_model"] = {"error": "Missing vision_model_query"}
            
    else:
        print(f"Unknown or unsupported scan method: {method}")
        analysis_result_dict["error"] = f"Unknown or unsupported scan method: {method}"
        analysis_result_dict["original_method"] = method

    print("\nFinal analysis result:")
    print(json.dumps(analysis_result_dict, indent=4))
    
   
    response = scan_inital_prompt(prompt, {"scan": True, "ui_screen": analysis_result_dict, "method": method})
    print("Initial classification response:")
    print(json.dumps(response, indent=4))
    
if response.get("classification") == "REFUSED":
    print("Refused to scan the screen:")
    print(response.get("reason"))
    exit()