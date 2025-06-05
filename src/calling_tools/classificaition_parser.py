import json

def parse_llm_classification_output(llm_output_str: str) -> dict:
    """
    Parses the LLM's JSON output to extract the task classification and related data.

    Args:
        llm_output_str: The raw string output from the LLM, expected to be a JSON object
                        potentially wrapped in markdown or other tags.

    Returns:
        A dictionary containing the classification details.
        Example for SIMPLE: {"classification": "SIMPLE"}
        Example for SCAN: {"classification": "SCAN", "method": "Omni Parser"}
        Example for REFUSED: {"classification": "REFUSED", "reason": "..."}
        Example for CONVERSATIONAL: {"classification": "CONVERSATIONAL", "response": "..."}
        Returns {"classification": "ERROR", "error": "description", "raw_output": ...} on failure.
    """
    try:
        # Attempt to extract JSON from potentially messy LLM output
        json_block = llm_output_str.strip()

        # Handle <scanner> tags if present
        # if "<scanner>" in json_block and "</scanner>" in json_block:
        #     start_index = json_block.find("<scanner>") + len("<scanner>")
        #     end_index = json_block.rfind("</scanner>") # Use rfind for potentially nested/malformed
        #     if end_index > start_index:
        #          json_block = json_block[start_index:end_index].strip()
        #     # If tags are malformed, it might fail at json.loads, which is handled.

        # Handle common markdown code blocks for JSON
        if json_block.startswith("```json"):
            json_block = json_block[len("```json"):].strip()
            if json_block.endswith("```"):
                json_block = json_block[:-len("```")].strip()
        elif json_block.startswith("```"): # Generic code block
            json_block = json_block[len("```"):].strip()
            if json_block.endswith("```"):
                json_block = json_block[:-len("```")].strip()
        
        # Fallback: try to find the first '{' and last '}'
        # This is a bit risky if there's other JS-like content, but can help for simple cases.
        if not json_block.startswith("{") and "{" in json_block:
            first_brace = json_block.find("{")
            last_brace = json_block.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_block = json_block[first_brace : last_brace + 1]

        data = json.loads(json_block)

        classification = data.get("classification")
        if not classification:
            return {"classification": "ERROR", "error": "Missing 'classification' key in LLM output.", "raw_output": llm_output_str}

        result = {"classification": classification}

        if classification == "REFUSED":
            result["reason"] = data.get("reason", "No reason provided.")
        elif classification == "CONVERSATIONAL":
            result["response"] = data.get("response", "No response provided.")
        elif classification == "SCAN":
            result["method"] = data.get("method")
            if not result["method"]:
                 return {"classification": "ERROR", "error": "Missing 'method' key for SCAN classification.", "raw_output": llm_output_str}
            if result["method"] == "Omni Parser + Vision Model":
                result["vision_model_query"] = data.get("vision_model_query")
                if not result["vision_model_query"]:
                    return {"classification": "ERROR", "error": "Missing 'vision_model_query' for SCAN with Vision Model.", "raw_output": llm_output_str}
        
        # For HTN and SIMPLE, only classification is typically expected based on prompts.
        # Any extra fields will be ignored unless specified above.

        return result

    except json.JSONDecodeError as e:
        return {"classification": "ERROR", "error": f"Invalid JSON output from LLM: {str(e)}", "raw_output": llm_output_str}
    except Exception as e: # Catch any other unexpected errors
        return {"classification": "ERROR", "error": f"An unexpected error occurred during parsing: {str(e)}", "raw_output": llm_output_str}

def parse_l2_output(llm_output_str: str) -> dict:
    """
    Parses the LLM's JSON output for L2 task plans.

    Args:
        llm_output_str: The raw string output from the LLM, expected to be a JSON object
                        potentially wrapped in markdown or other tags, containing 'steps' and 'end' keys.

    Returns:
        A dictionary containing the L2 task plan details.
        Returns {"error": "description", "raw_output": ...} on parsing failure or if format is unexpected.
    """
    try:
        json_block = llm_output_str.strip()

        # Handle common markdown code blocks for JSON
        if json_block.startswith("```json"):
            json_block = json_block[len("```json"):].strip()
            if json_block.endswith("```"):
                json_block = json_block[:-len("```")].strip()
        elif json_block.startswith("```"): # Generic code block
            json_block = json_block[len("```"):].strip()
            if json_block.endswith("```"):
                json_block = json_block[:-len("```")].strip()
        
        # Fallback: try to find the first '{' and last '}'
        if not json_block.startswith("{") and "{" in json_block:
            first_brace = json_block.find("{")
            last_brace = json_block.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_block = json_block[first_brace : last_brace + 1]

        data = json.loads(json_block)

        # Validate L2 specific keys
        if "steps" not in data or "end" not in data:
            return {"error": "L2 output missing 'steps' or 'end' key.", "raw_output": llm_output_str}
        
        return data

    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON output from LLM for L2 parser: {str(e)}", "raw_output": llm_output_str}
    except Exception as e: # Catch any other unexpected errors
        return {"error": f"An unexpected error occurred during L2 parsing: {str(e)}", "raw_output": llm_output_str}

def parse_l1_output(llm_output_str: str) -> dict:
    """
    Parses the LLM's JSON output for L1 actions.

    Args:
        llm_output_str: The raw string output from the LLM, expected to be a JSON object
                        potentially wrapped in markdown or other tags, containing a 'classification' key.

    Returns:
        A dictionary containing the L1 action details.
        Returns {"error": "description", "raw_output": ...} on parsing failure or if format is unexpected.
    """
    try:
        json_block = llm_output_str.strip()

        if json_block.startswith("```json"):
            json_block = json_block[len("```json"):].strip()
            if json_block.endswith("```"):
                json_block = json_block[:-len("```")].strip()
        elif json_block.startswith("```"):
            json_block = json_block[len("```"):].strip()
            if json_block.endswith("```"):
                json_block = json_block[:-len("```")].strip()
        
        if not json_block.startswith("{") and "{" in json_block:
            first_brace = json_block.find("{")
            last_brace = json_block.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_block = json_block[first_brace : last_brace + 1]

        data = json.loads(json_block)

        classification = data.get("classification")
        if not classification:
            return {"error": "L1 output missing 'classification' key.", "raw_output": llm_output_str}

        # Normalize classification to handle common LLM variations (e.g., VMTOOLS vs VM_TOOLS)
        if classification.upper() == "VMTOOLS":
            classification = "VM_TOOLS"
        data["classification"] = classification # Update the data dict with the normalized classification

        # Basic validation for L1 classifications
        if classification == "VM_TOOLS": # Ensure this check is against the normalized form
            if "operations" not in data or not isinstance(data["operations"], list):
                return {"error": "VM_TOOLS output missing 'operations' list or not a list.", "raw_output": llm_output_str}
            
            for i, op in enumerate(data["operations"]):
                # --- START OF NEW TRANSFORMATION LOGIC ---
                # Transform LLM's 'keyboard' operation to 'input' action
                if op.get("operation") == "keyboard":
                    op["type"] = "action"
                    op["action_name"] = "input"
                    parameters = {"type": "hotkey"}
                    key = op.get("key")
                    modifiers = op.get("modifiers")

                    if modifiers:
                        parameters["content"] = modifiers + [key]
                    else:
                        parameters["content"] = key
                    op["parameters"] = parameters
                    # Remove original keys that are now replaced or remapped
                    for k_to_remove in ["operation", "action", "key", "modifiers"]:
                        op.pop(k_to_remove, None)
                # Transform LLM's 'wait' operation to 'sleep' type
                elif op.get("operation") == "wait":
                    op["type"] = "sleep"
                    # Assuming duration is in milliseconds based on common LLM outputs and template examples
                    op["duration_ms"] = op.get("duration")
                    # Remove original keys
                    for k_to_remove in ["operation", "duration"]:
                        op.pop(k_to_remove, None)
                
                # Ensure type is set if not already handled by explicit mapping above
                if "type" not in op:
                    action_name_candidate = op.get("operation")
                    if action_name_candidate == "sleep":
                        op["type"] = "sleep"
                    elif action_name_candidate: # Default to action if operation is present and not sleep
                        op["type"] = "action"
                
                # Ensure action_name is set for action types
                if op.get("type") == "action" and "action_name" not in op:
                    op["action_name"] = op.get("operation") # This covers cases like moveto, scroll, etc.
                    # If 'parameters' is not explicitly defined but other keys exist, infer them
                    if "parameters" not in op and isinstance(op, dict):
                        inferred_params = {k: v for k, v in op.items() if k not in ["type", "action_name", "operation"]}
                        if inferred_params:
                            op["parameters"] = inferred_params
                            # Clean up inferred parameters from the top level
                            for k_to_remove in inferred_params.keys():
                                op.pop(k_to_remove, None)
                
                # Additional validation for sleep operations after potential transformation
                if op.get("type") == "sleep":
                    if "duration_ms" not in op or not isinstance(op["duration_ms"], (int, float)) or op["duration_ms"] <= 0:
                        return {"error": f"VM_TOOLS sleep operation {i} missing positive integer 'duration_ms'. Op: {op}", "raw_output": llm_output_str}
                    op["duration_ms"] = int(op["duration_ms"]) # Ensure it's an integer
                # --- END OF NEW TRANSFORMATION LOGIC ---

                # Re-assign op_type, action_name, and parameters after potential transformation
                op_type = op.get("type")
                action_name = op.get("action_name")
                parameters = op.get("parameters")

                # Ensure op_type is now valid after potential transformation
                if op_type not in ["action", "sleep"]:
                    return {"error": f"VM_TOOLS operation {i} has invalid or missing type: {op_type}. Must be 'action' or 'sleep'.", "raw_output": llm_output_str}

                if op_type == "action":
                    if not action_name or not parameters or not isinstance(parameters, dict):
                        return {"error": f"VM_TOOLS action operation {i} missing 'action_name' or 'parameters', or parameters not a dict. Op: {op}", "raw_output": llm_output_str}
                    
                    # Validate specific action parameters (basic check for presence)
                    if action_name == "moveto":
                        if "x" not in parameters or "y" not in parameters:
                            return {"error": f"VM_TOOLS moveto operation {i} missing 'x' or 'y' parameters. Op: {op}", "raw_output": llm_output_str}
                    elif action_name == "moverel":
                        if "direction" not in parameters:
                            return {"error": f"VM_TOOLS moverel operation {i} missing 'direction' parameter. Op: {op}", "raw_output": llm_output_str}
                    elif action_name == "input": # This is now the target for keyboard operations
                        if "type" not in parameters or "content" not in parameters:
                            return {"error": f"VM_TOOLS input operation {i} missing 'type' or 'content' parameters. Op: {op}", "raw_output": llm_output_str}
                        # Additional validation for 'input' type
                        if parameters["type"] not in ["text", "hotkey"]:
                             return {"error": f"VM_TOOLS input operation {i} has invalid 'type' parameter. Must be 'text' or 'hotkey'. Op: {op}", "raw_output": llm_output_str}
                        if parameters["type"] == "hotkey" and not (isinstance(parameters["content"], str) or (isinstance(parameters["content"], list) and all(isinstance(x, str) for x in parameters["content"]))):
                            return {"error": f"VM_TOOLS hotkey input operation {i} 'content' must be a string or list of strings. Op: {op}", "raw_output": llm_output_str}
                    elif action_name == "scroll":
                        if "direction" not in parameters:
                            return {"error": f"VM_TOOLS scroll operation {i} missing 'direction' parameter. Op: {op}", "raw_output": llm_output_str}
                    elif action_name == "changewmctrlinfo":
                        if "id" not in parameters:
                            return {"error": f"VM_TOOLS changewmctrlinfo operation {i} missing 'id' parameter. Op: {op}", "raw_output": llm_output_str}
                    else:
                        # This should now only catch genuinely unsupported action_names
                        return {"error": f"VM_TOOLS action operation {i} has unknown action_name: {action_name}. This action might not be supported by VM_TOOLS. Op: {op}", "raw_output": llm_output_str}

                # Removed old sleep validation block as it's handled by new transformation and validation above
                # elif op_type == "sleep":
                #     pass 
        elif classification == "SCAN":
            if "method" not in data:
                return {"error": "SCAN output missing 'method'.", "raw_output": llm_output_str}
        elif classification == "L1_FAILURE_ESCALATION":
            if "failure_report" not in data:
                return {"error": "L1_FAILURE_ESCALATION output missing 'failure_report'.", "raw_output": llm_output_str}
        # STEP_COMPLETE and INPUT_REQUEST can be simple

        return data

    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON output from LLM for L1 parser: {str(e)}", "raw_output": llm_output_str}
    except Exception as e:
        return {"error": f"An unexpected error occurred during L1 parsing: {str(e)}", "raw_output": llm_output_str}
