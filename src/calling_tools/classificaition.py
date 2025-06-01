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
