from .llm import LLM
from jinja2 import Template, Environment, FileSystemLoader
from google.genai import types
import json
import os
from dotenv import load_dotenv

from .screen import VM
from .prompt_j2_management import analyse_genesis_classification, get_system_l2_prompt, get_system_l1_prompt
from .calling_tools.classificaition_parser import parse_llm_classification_output, parse_l2_output, parse_l1_output
from .calling_tools.images.scan import OmniParser
from .calling_tools.images.vision_model import VisionModel

def _perform_scan_and_analysis(vm_instance: VM, omni_parser_instance: OmniParser, vision_model_instance: VisionModel, method: str, vision_model_query: str = None) -> dict:
    analysis_result_dict = {}
    try:
        screenshot_bytes = vm_instance.screenshot()
        print(f"Screenshot captured successfully ({len(screenshot_bytes)} bytes).")
    except Exception as e:
        print(f"✗ Failed to capture screenshot: {e}")
        return {"error": "Screenshot capture failed", "details": str(e)}

    if method == "OmniParser":
        print("Analyzing with Omni Parser...")
        omni_success, omni_ui_class, omni_ui_elements = omni_parser_instance.analyze_screenshot_data(screenshot_bytes, save_locally=False)
        analysis_result_dict["omni_parser"] = {
            "success": omni_success,
            "ui_classification": omni_ui_class,
            "ui_elements": omni_ui_elements
        }
        if not omni_success:
            print("OmniParser analysis did not report success.")

    elif method == "VisionModel":
        print("Analyzing with Vision Model...")
        vision_output = vision_model_instance.analyze(screenshot_bytes, vision_model_query)
        analysis_result_dict["vision_model"] = vision_output

    elif method == "OmniParserVisionModel":
        print("Analyzing with Omni Parser...")
        omni_success, omni_ui_class, omni_ui_elements = omni_parser_instance.analyze_screenshot_data(screenshot_bytes, save_locally=False)
        analysis_result_dict["omni_parser"] = {
            "success": omni_success,
            "ui_classification": omni_ui_class,
            "ui_elements": omni_ui_elements
        }
        if not omni_success:
            print("OmniParser analysis did not report success. Vision Model analysis will still be attempted if a query is available.")
        
        if vision_model_query:
            print("Analyzing with Vision Model...")
            vision_output = vision_model_instance.analyze(screenshot_bytes, vision_model_query)
            analysis_result_dict["vision_model"] = vision_output
        else:
            print("Warning: No vision_model_query provided for 'Omni Parser + Vision Model' method, though it was expected. Skipping Vision Model analysis.")
            analysis_result_dict["vision_model"] = {"error": "Missing vision_model_query"}
            
    else:
        print(f"Unknown or unsupported scan method: {method}")
        analysis_result_dict["error"] = f"Unknown or unsupported scan method: {method}"
        analysis_result_dict["original_method"] = method

    return analysis_result_dict

def scan_inital_prompt(user_input: str, context: dict = None, vm_instance: VM = None) -> dict:
    prompt_sys_genesis_classification = analyse_genesis_classification(context, vm_instance)
    llm_response = LLM.run(
        prompt_sys_genesis_classification,
        user_input,
        config=types.GenerateContentConfig(
            temperature=1,
            candidate_count=1,
            max_output_tokens=8192,
            top_p=0.95,
        ),
        force_json_output=True
    )
    return parse_llm_classification_output(llm_response)

def stage1(user_prompt: str, vm_instance: VM, omni_parser_instance: OmniParser, vision_model_instance: VisionModel) -> dict:
    response = scan_inital_prompt(user_prompt, None, vm_instance)
    print("Initial classification response:")
    print(json.dumps(response, indent=4))
    
    if response.get("classification") == "SCAN":
        method = response.get("method")
        vision_model_query = response.get("vision_model_query")

        analysis_result_dict = _perform_scan_and_analysis(vm_instance, omni_parser_instance, vision_model_instance, method, vision_model_query)
        if "error" in analysis_result_dict:
            print("\nFinal analysis result (error during scan):")
            print(json.dumps(analysis_result_dict, indent=4))
            return {"classification": "ERROR", "details": analysis_result_dict["error"], "original_error": analysis_result_dict.get("details", "")}

        print("\nFinal analysis result:")
        print(json.dumps(analysis_result_dict, indent=4))

        response = scan_inital_prompt(user_prompt, {"scan": True, "ui_screen": analysis_result_dict, "method": method}, vm_instance)
        print("Initial classification response:")
        print(json.dumps(response, indent=4))

    return response

def stage_l2(user_prompt: str, vm_instance: VM) -> dict:
    wmctrlinfo = vm_instance.get_wmctrl_info()
    context_for_l2_prompt = {
        "task": user_prompt,
        "wmctrlinfo": wmctrlinfo
    }
    l2_prompt = get_system_l2_prompt(context_for_l2_prompt)
    llm_response = LLM.run(
        l2_prompt,
        user_prompt, # The user_prompt also acts as the specific instruction for the LLM in this context
        config=types.GenerateContentConfig(
            temperature=1,
            candidate_count=1,
            max_output_tokens=8192,
            top_p=0.95,
        ),
        force_json_output=True
    )
    print(f"\nRaw L2 LLM response: {llm_response}") # Log raw L2 LLM response
    # Assuming the L2 response will be a JSON string that needs parsing
    parsed_l2_response = parse_l2_output(llm_response)
    if "error" in parsed_l2_response:
        print(f"Warning: L2 LLM response parsing failed. Raw response: {llm_response}")
        return {"classification": "ERROR", "details": parsed_l2_response["error"], "raw_response": parsed_l2_response["raw_response"]}
    return parsed_l2_response

def stage_l1(task_step: dict, vm_instance: VM, omni_parser_instance: OmniParser, vision_model_instance: VisionModel, prev_l1_actions: list = None, next_l2_steps: list = None) -> dict:
    wmctrlinfo = vm_instance.get_wmctrl_info()
    
    context_for_l1_prompt = {
        "task_step": task_step,
        "wmctrlinfo": wmctrlinfo,
        "prev_l1_actions": prev_l1_actions,
        "next_l2_steps": next_l2_steps
    }
    l1_prompt = get_system_l1_prompt(context_for_l1_prompt)
    llm_response = LLM.run(
        l1_prompt,
        task_step.get("description", ""), # Use the description of the task step as user prompt
        config=types.GenerateContentConfig(
            temperature=0.3,
            candidate_count=1,
            max_output_tokens=8192,
            top_p=0.95,
        ),
        force_json_output=True
    )
    print(f"\nRaw L1 LLM response: {llm_response}") # Log raw L1 LLM response

    parsed_l1_response = parse_l1_output(llm_response)

    if "error" in parsed_l1_response:
        print(f"Warning: L1 LLM response parsing failed. Raw response: {llm_response}")
        return {"classification": "ERROR", "details": parsed_l1_response["error"], "raw_response": parsed_l1_response["raw_output"]}

    classification = parsed_l1_response.get("classification")

    if classification == "VM_TOOLS":
        operations = parsed_l1_response.get("operations", [])
        print(f"Executing VM_TOOLS operations: {json.dumps(operations, indent=4)}")
        # In a real scenario, you'd call vm_instance.run_operations(operations)
        vm_operations_results = vm_instance.run_operations(operations)
        print(f"VM_TOOLS operations results: {json.dumps(vm_operations_results, indent=4)}")

        # After operations, L1 would typically re-verify, possibly with a scan
        # For simplicity, we'll assume success and need a re-classification
        # A more robust system would check vm_operations_results for success/failure of each op
        all_succeeded = all(res.get("success", False) for res in vm_operations_results)
        if all_succeeded:
            return {"classification": "NEEDS_VERIFICATION", "last_vm_operations_results": vm_operations_results}
        else:
            return {"classification": "L1_FAILURE_ESCALATION", "failure_report": {"original_l2_step": task_step, "vm_tools_operations_attempted": operations, "l1_summary_of_failure": "Some VM_TOOLS operations failed", "vm_operations_results": vm_operations_results}}

    elif classification == "SCAN":
        method = parsed_l1_response.get("method")
        area = parsed_l1_response.get("area")
        vision_model_query = parsed_l1_response.get("vision_model_query")
        
        print(f"Performing L1 scan with method: {method}, area: {area}, query: {vision_model_query}")
        scan_result = _perform_scan_and_analysis(vm_instance, omni_parser_instance, vision_model_instance, method, vision_model_query)
        if "error" in scan_result:
            return {"classification": "ERROR", "details": "L1 scan failed", "original_error": scan_result["error"]}
        
        # After scan, L1 would typically analyze scan results against expected_success_indicators
        # For simplicity, we'll assume the scan itself is the action and needs re-evaluation by LLM
        return {"classification": "NEEDS_VERIFICATION", "scan_output": scan_result}

    elif classification == "STEP_COMPLETE":
        print("L1 reports step as complete.")
        return {"classification": "STEP_COMPLETE"}

    elif classification == "L1_FAILURE_ESCALATION":
        print("L1 is escalating failure to L2.")
        return parsed_l1_response # This contains the full failure report

    elif classification == "INPUT_REQUEST":
        print("L1 is requesting input from the user.")
        return parsed_l1_response # This contains the input request details

    else:
        print(f"Unknown L1 classification: {classification}")
        return {"classification": "ERROR", "details": f"Unknown L1 classification: {classification}", "raw_response": llm_response}

if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    # prompt = "fix this error on my screen"

    load_dotenv()
    omniparser_url = os.getenv("OMNI_URL")
    omniParser = OmniParser(omniparser_url)
    visionModel = VisionModel()
    vm = VM("192.168.1.64", 6969)

    initial_classification_response = stage1(prompt, vm, omniParser, visionModel)

    if initial_classification_response.get("classification") == "REFUSED":
        print("Refused to scan the screen:")
        print(initial_classification_response.get("reason"))
        exit()
    elif initial_classification_response.get("classification") == "ERROR":
        print(f"An error occurred during stage1: {initial_classification_response.get('details')}")
        if initial_classification_response.get('original_error'):
            print(f"Original error: {initial_classification_response.get('original_error')}")
        exit()
    elif initial_classification_response.get("classification") == "SIMPLE":
        print("\nInitial classification: SIMPLE. Proceeding to Stage L2 for task planning...")
        l2_response = stage_l2(prompt, vm)
        
        if "error" in l2_response:
            print(f"Error during L2 stage: {l2_response.get("details", "Unknown error")}")
            if l2_response.get("raw_response"):
                print(f"Raw L2 response: {l2_response["raw_response"]}")
            exit()

        steps = l2_response.get("steps", [])
        if not steps:
            print("L2 returned no steps. Exiting.")
            exit()

        print("\nL2 Stage response (parsed steps):")
        for i, step in enumerate(steps):
            print(f"  Step {i+1}: {step.get("description", "No description")}")
        print(json.dumps(l2_response, indent=4))
        
        print("\nProceeding to Stage L1 to execute steps...")
        for i, step in enumerate(steps):
            print(f"\nExecuting L1 step {i+1}: {step.get("description", "")}")
            l1_result = stage_l1(step, vm, omniParser, visionModel, prev_l1_actions=None, next_l2_steps=steps[i+1:])
            
            if l1_result.get("classification") == "STEP_COMPLETE":
                print(f"L1 Step {i+1} completed successfully.")
            elif l1_result.get("classification") == "ERROR":
                print(f"Error during L1 step {i+1}: {l1_result.get("details", "Unknown error")}")
                if l1_result.get("raw_response"):
                    print(f"Raw L1 response: {l1_result["raw_response"]}")
                exit()
            elif l1_result.get("classification") == "L1_FAILURE_ESCALATION":
                print(f"L1 Step {i+1} escalated failure to L2. Report: {json.dumps(l1_result.get("failure_report", {}), indent=4)}")
                exit()
            elif l1_result.get("classification") == "INPUT_REQUEST":
                print(f"L1 Step {i+1} requested user input. Request: {json.dumps(l1_result.get("input_needed", {}), indent=4)}")
                exit()
            elif l1_result.get("classification") == "NEEDS_VERIFICATION":
                # L1 executed an action and needs L2 to re-evaluate or verify
                # This is a simplified loop. In a full system, L2 would re-prompt LLM for next action.
                print(f"L1 Step {i+1} needs further verification or action from L2. L1 Result: {json.dumps(l1_result, indent=4)}")
            else:
                print(f"Unexpected result from L1 step {i+1}: {json.dumps(l1_result, indent=4)}")

        print("All L2 steps attempted.")
        exit()
    else:
        print("\nFinal classification response from stage1:")
        print(json.dumps(initial_classification_response, indent=4))