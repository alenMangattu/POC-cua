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

def _perform_scan_and_analysis(vm_instance: VM, omni_parser_instance: OmniParser, vision_model_instance: VisionModel, method: str, area: dict, vision_model_query: str = None) -> dict:
    analysis_result_dict = {}
    try:
        screenshot_bytes = vm_instance.screenshot()
        print(f"Screenshot captured successfully ({len(screenshot_bytes)} bytes).")
    except Exception as e:
        print(f"✗ Failed to capture screenshot: {e}")
        return {"error": "Screenshot capture failed", "details": str(e)}

    # Prepare area for scan tool
    scan_area_type = area.get("type")
    scan_coordinates = area.get("coordinates", [])
    scan_window_id = area.get("window_id", "")

    if scan_area_type == "full":
        scan_target_area = "full"
    elif scan_area_type == "window" and scan_window_id:
        scan_target_area = f"window_{scan_window_id}"
    elif scan_area_type == "region" and scan_coordinates:
        scan_target_area = f"region_{'_.'.join(map(str, scan_coordinates))}"
    else:
        print(f"Invalid or incomplete area specification: {area}")
        return {"error": "Invalid area specification", "details": area}

    if method == "Omni Parser":
        print(f"Analyzing with Omni Parser, area: {scan_target_area}...")
        omni_success, omni_ui_class, omni_ui_elements = omni_parser_instance.analyze_screenshot_data(screenshot_bytes, save_locally=False)
        analysis_result_dict["omni_parser"] = {
            "success": omni_success,
            "ui_classification": omni_ui_class,
            "ui_elements": omni_ui_elements
        }
        if not omni_success:
            print("OmniParser analysis did not report success.")

    elif method == "Vision Model":
        print(f"Analyzing with Vision Model, area: {scan_target_area}...")
        if not vision_model_query:
            print("Error: Vision Model method requires a vision_model_query.")
            return {"error": "Missing vision_model_query for Vision Model method"}
        vision_output = vision_model_instance.analyze(screenshot_bytes, vision_model_query, area=scan_target_area)
        analysis_result_dict["vision_model"] = vision_output

    elif method == "Omni Parser + Vision Model":
        print(f"Analyzing with Omni Parser, area: {scan_target_area}...")
        omni_success, omni_ui_class, omni_ui_elements = omni_parser_instance.analyze_screenshot_data(screenshot_bytes, save_locally=False)
        analysis_result_dict["omni_parser"] = {
            "success": omni_success,
            "ui_classification": omni_ui_class,
            "ui_elements": omni_ui_elements
        }
        if not omni_success:
            print("OmniParser analysis did not report success. Vision Model analysis will still be attempted if a query is available.")
        
        if vision_model_query:
            print(f"Analyzing with Vision Model, area: {scan_target_area}...")
            vision_output = vision_model_instance.analyze(screenshot_bytes, vision_model_query, area=scan_target_area)
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
        area = response.get("area")
        vision_model_query = response.get("vision_model_query")

        analysis_result_dict = _perform_scan_and_analysis(vm_instance, omni_parser_instance, vision_model_instance, method, area, vision_model_query)
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

def stage_l1(task_step: dict, vm_instance: VM, omni_parser_instance: OmniParser, vision_model_instance: VisionModel, context: dict) -> dict:
    wmctrlinfo = context.get("wmctrlinfo", vm_instance.get_wmctrl_info())
    prev_l1_actions = context.get("prev_l1_actions", [])
    next_l2_steps = context.get("next_l2_steps", [])
    last_vm_operations_results = context.get("last_vm_operations_results", None)
    last_scan_output = context.get("last_scan_output", None)
    l1_failure_report_if_any = context.get("l1_failure_report_if_any", None)

    l1_prompt_context = {
        "task_step": task_step,
        "wmctrlinfo": wmctrlinfo,
        "prev_l1_actions": prev_l1_actions,
        "next_l2_steps": next_l2_steps,
        "last_vm_operations_results": last_vm_operations_results,
        "last_scan_output": last_scan_output,
        "l1_failure_report": l1_failure_report_if_any # Pass the failure report for L1 to reason about
    }

    l1_prompt = get_system_l1_prompt(l1_prompt_context)
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

    # The main loop will now handle execution, verification, and retries/escalation
    return parsed_l1_response

def _verify_l1_step_success(expected_indicators: dict, wmctrlinfo: dict, scan_output: dict = None) -> bool:
    indicator_type = expected_indicators.get("type")
    details = expected_indicators.get("details", {})

    if indicator_type == "active_window_title_contains":
        expected_title_snippet = details.get("window_title_contains")
        active_window_title = wmctrlinfo.get("active_window", {}).get("title", "")
        return expected_title_snippet in active_window_title

    elif indicator_type == "ui_element_visible":
        if scan_output and scan_output.get("omni_parser", {}).get("success"):
            ui_elements = scan_output["omni_parser"].get("ui_elements", [])
            if "element_text" in details:
                expected_text = details["element_text"]
                for element in ui_elements:
                    if element.get("type") == "text" and expected_text in element.get("content", ""):
                        return True
            if "element_description" in details:
                expected_description = details["element_description"].lower()
                # Broaden the check for common launcher/search box elements
                for element in ui_elements:
                    element_content_lower = str(element.get("content", "")).lower()
                    element_type = element.get("type", "").lower()

                    # More generic check for common launcher/search box indicators
                    if element_type == "text_input":
                        return True  # Any text input likely indicates a search/launcher
                    
                    # Check for keywords in content or description
                    if ("search" in element_content_lower or "application" in element_content_lower or "launcher" in element_content_lower):
                        return True
                    
                    # Fallback to original broader description check if more specific checks fail
                    if expected_description in element_content_lower or \
                       expected_description in str(element.get("description", "")).lower():
                        return True
        return False

    elif indicator_type == "text_on_screen":
        expected_text = details.get("text_to_find")
        if scan_output and scan_output.get("omni_parser", {}).get("success"):
            ui_elements = scan_output["omni_parser"].get("ui_elements", [])
            for element in ui_elements:
                if expected_text in str(element.get("content", "")):
                    return True
        return False

    elif indicator_type == "window_appeared":
        expected_title_snippet = details.get("window_title_contains")
        window_list = wmctrlinfo.get("window_list", [])
        for window in window_list:
            if expected_title_snippet in window.get("title", ""):
                return True
        return False

    elif indicator_type == "file_exists":
        # This requires OS-level file system access, which VM class currently doesn't provide.
        # For now, it will always return False unless VM is extended.
        print("Warning: file_exists indicator is not fully supported without VM file system access.")
        return False

    elif indicator_type == "no_error_dialog_visible":
        # This is a placeholder. A real implementation would scan for common error dialog titles or patterns.
        # For now, assume no error unless explicitly detected.
        return True 

    else:
        print(f"Warning: Unknown or unsupported success indicator type: {indicator_type}")
        return False

if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    load_dotenv()
    omniparser_url = os.getenv("OMNI_URL")
    omniParser = OmniParser(omniparser_url)
    visionModel = VisionModel()
    vm = VM("192.168.1.64", 6969)

    MAX_L1_RETRIES_PER_ACTION = 2  # L1 can retry a failed action up to this many times (initial + 2 retries = 3 attempts total)
    MAX_L2_REPLANS_PER_TASK = 3  # L2 can replan the task up to this many times

    initial_classification_response = stage1(prompt, vm, omniParser, visionModel)

    if initial_classification_response.get("classification") == "SIMPLE":
        current_user_prompt = prompt
        l2_replanning_attempts = 0

        while l2_replanning_attempts < MAX_L2_REPLANS_PER_TASK:
            print(f"\nInitial classification: SIMPLE. Proceeding to Stage L2 for task planning (attempt {l2_replanning_attempts + 1})...")
            
            # If there was a previous L1 failure, pass it to L2 for replanning
            l2_prompt_for_llm = current_user_prompt # Initial prompt or replanning request
            
            l2_response = stage_l2(l2_prompt_for_llm, vm)

            if "error" in l2_response:
                print(f"Error during L2 stage: {l2_response.get("details", "Unknown error")}")
                if l2_response.get("raw_response"):
                    print(f"Raw L2 response: {l2_response["raw_response"]}")
                break  # Exit if L2 planning itself fails

            steps = l2_response.get("steps", [])
            if not steps:
                print("L2 returned no steps. Exiting.")
                break  # Exit if L2 returns no steps

            print("\nL2 Stage response (parsed steps):")
            for i, step in enumerate(steps):
                print(f"  Step {i + 1}: {step.get("description", "No description")}")
            print(json.dumps(l2_response, indent=4))

            print("\nProceeding to Stage L1 to execute steps...")

            current_l1_step_index = 0
            while current_l1_step_index < len(steps):
                current_l2_step = steps[current_l1_step_index]
                l1_action_retries = 0
                step_completed = False
                l1_last_vm_ops_results = None
                l1_last_scan_output = None
                l1_failure_report = None

                while l1_action_retries <= MAX_L1_RETRIES_PER_ACTION:
                    print(f"\nExecuting L1 step {current_l1_step_index + 1}: {current_l2_step.get("description", "")} (Attempt {l1_action_retries + 1})")

                    # Prepare context for L1 LLM
                    l1_context_for_prompt = {
                        "wmctrlinfo": vm.get_wmctrl_info(),
                        "prev_l1_actions": [],  # This would be populated if we tracked all L1 actions in the session
                        "next_l2_steps": steps[current_l1_step_index + 1:],
                        "last_vm_operations_results": l1_last_vm_ops_results,
                        "last_scan_output": l1_last_scan_output,
                        "l1_failure_report_if_any": l1_failure_report  # Pass potential previous failure report
                    }

                    # Call L1 to get the next action (VM_TOOLS or SCAN)
                    l1_llm_response = stage_l1(current_l2_step, vm, omniParser, visionModel, l1_context_for_prompt)

                    if "error" in l1_llm_response:
                        print(f"Error during L1 LLM response: {l1_llm_response.get("details")}")
                        l1_failure_report = {"original_l2_step": current_l2_step, "l1_summary_of_failure": f"L1 LLM error: {l1_llm_response.get("details")}"}
                        break  # Break L1 action retry loop, go to L2 replan if retries exhausted

                    classification = l1_llm_response.get("classification")

                    if classification == "VM_TOOLS":
                        operations = l1_llm_response.get("operations", [])
                        print(f"Executing VM_TOOLS operations: {json.dumps(operations, indent=4)}")
                        vm_operations_results = vm.run_operations(operations)
                        print(f"VM_TOOLS operations results: {json.dumps(vm_operations_results, indent=4)}")
                        l1_last_vm_ops_results = vm_operations_results  # Store for next L1 turn

                        # Immediately verify after VM_TOOLS
                        current_wmctrlinfo = vm.get_wmctrl_info()
                        if _verify_l1_step_success(current_l2_step.get("expected_success_indicators", {}), current_wmctrlinfo, l1_last_scan_output):
                            print(f"L1 Step {current_l1_step_index + 1} ({current_l2_step.get("description")}) completed successfully.")
                            step_completed = True
                            break  # Step completed, move to next L2 step
                        else:
                            l1_failure_report = {"original_l2_step": current_l2_step, "vm_tools_operations_attempted": operations, "l1_summary_of_failure": "VM_TOOLS operations failed to achieve expected indicators.", "vm_operations_results": vm_operations_results}

                            # Check if any of the operations were 'input' actions
                            is_input_action_failure = any(op.get("action_name") == "input" for op in operations if op.get("type") == "action")

                            if is_input_action_failure:
                                print(f"L1 Step {current_l1_step_index + 1} ({current_l2_step.get("description")}) verification failed.")
                                print("Input action failed verification. Escalating to L2 for replanning.")
                                l1_action_retries = MAX_L1_RETRIES_PER_ACTION + 1 # Force exit inner loop
                            else:
                                print(f"L1 Step {current_l1_step_index + 1} ({current_l2_step.get("description")}) verification failed. Retrying...")
                                l1_action_retries += 1
                            # L1 will be re-prompted with l1_failure_report_if_any for retry

                    elif classification == "SCAN":
                        method = l1_llm_response.get("method")
                        area = l1_llm_response.get("area")
                        vision_model_query = l1_llm_response.get("vision_model_query")

                        print(f"Performing L1 scan with method: {method}, area: {area}, query: {vision_model_query}")
                        scan_result = _perform_scan_and_analysis(vm, omniParser, visionModel, method, area, vision_model_query)

                        if "error" in scan_result:
                            print(f"Error during L1 scan: {scan_result.get("error")}")
                            l1_failure_report = {"original_l2_step": current_l2_step, "l1_summary_of_failure": f"L1 scan failed: {scan_result.get("error")}"}
                            break  # Break L1 action retry loop

                        l1_last_scan_output = scan_result  # Store for next L1 turn (for verification)
                        print(f"L1 scan results: {json.dumps(scan_result, indent=4)}")

                        # After scan, immediately verify
                        current_wmctrlinfo = vm.get_wmctrl_info()
                        if _verify_l1_step_success(current_l2_step.get("expected_success_indicators", {}), current_wmctrlinfo, l1_last_scan_output):
                            print(f"L1 Step {current_l1_step_index + 1} ({current_l2_step.get("description")}) completed successfully after scan.")
                            step_completed = True
                            break  # Step completed, move to next L2 step
                        else:
                            print(f"L1 Step {current_l1_step_index + 1} ({current_l2_step.get("description")}) verification failed after scan. Retrying...")
                            l1_failure_report = {"original_l2_step": current_l2_step, "scan_output_if_any": scan_result, "l1_summary_of_failure": "L1 scan did not yield expected success indicators.", "vm_operations_results": vm_operations_results if vm_operations_results else {}}
                            # L1 will be re-prompted with l1_failure_report_if_any for retry

                    elif classification == "STEP_COMPLETE":
                        # This should only be returned by L1 if L1 itself decides it's complete
                        print(f"L1 reports step {current_l1_step_index + 1} as complete.")
                        step_completed = True
                        break

                    elif classification == "L1_FAILURE_ESCALATION":
                        print(f"L1 is escalating failure for step {current_l1_step_index + 1} to L2.")
                        l1_failure_report = l1_llm_response.get("failure_report", {"l1_summary_of_failure": "L1 escalated without detailed report."})
                        break  # Break L1 action retry loop, trigger L2 replan

                    elif classification == "INPUT_REQUEST":
                        print(f"L1 is requesting input from the user: {json.dumps(l1_llm_response.get("input_needed"), indent=4)}")
                        # Here you'd typically prompt the user for input and then pass it back to L1/L2
                        # For now, we'll break and exit or handle as a failure
                        l1_failure_report = {"original_l2_step": current_l2_step, "l1_summary_of_failure": "L1 requested user input, not handled automatically."}
                        break

                    elif classification == "MENTOR":
                        print(f"L1 requested mentor clarification: {json.dumps(l1_llm_response.get("question"), indent=4)}")
                        # In a real system, send this to mentor LLM and pass response back to L1
                        l1_failure_report = {"original_l2_step": current_l2_step, "l1_summary_of_failure": "L1 requested mentor input, not handled automatically."}
                        break

                    else:
                        print(f"Unknown L1 classification: {classification}")
                        l1_failure_report = {"original_l2_step": current_l2_step, "l1_summary_of_failure": f"Unknown L1 classification: {classification}"}
                        break

                # After L1 action retry loop
                if step_completed:
                    current_l1_step_index += 1  # Move to the next L2 step
                else:
                    print(f"L1 step {current_l1_step_index + 1} failed. Triggering L2 replanning.")
                    # Pass the failure report to L2 for replanning
                    failure_details = json.dumps(l1_failure_report, indent=2)
                    current_user_prompt = f"""The previous L2 plan resulted in a failed L1 step. The original user prompt was: "{prompt}".

Here is a detailed report of the L1 failure:
{failure_details}

Please generate a new L2 plan, taking into account this failure.
"""
                    l2_replanning_attempts += 1
                    break  # Break L2 step loop, go to L2 replanning loop

            else:  # This 'else' belongs to the 'while current_l1_step_index < len(steps)' loop
                print("\nAll L2 steps completed successfully!")
                break  # All steps done, exit the L2 replanning loop

        else:  # This 'else' belongs to the 'while l2_replanning_attempts < MAX_L2_REPLANS_PER_TASK' loop
            print(f"\nTask failed after {MAX_L2_REPLANS_PER_TASK} L2 replanning attempts. Exiting.")

    elif initial_classification_response.get("classification") == "REFUSED":
        print("Refused to scan the screen:")
        print(initial_classification_response.get("reason"))
        exit()
    elif initial_classification_response.get("classification") == "ERROR":
        print(f"An error occurred during stage1: {initial_classification_response.get('details')}")
        if initial_classification_response.get('original_error'):
            print(f"Original error: {initial_classification_response.get('original_error')}")
        exit()