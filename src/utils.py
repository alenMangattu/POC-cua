from typing import Any, Dict, Optional
from enum import Enum
import json
import re
from src.agent.tasks.task_models import Task
# Assuming Task and TaskStatus/TaskType Enums are defined elsewhere or passed as dictionary-like objects
# For this utility, we'll make it generic enough to handle dicts that might contain these Enums.

def task_to_json_dict(task: Task) -> Dict[str, Any]:
    """Converts a Task dataclass instance to a JSON-serializable dictionary."""
    if not isinstance(task, Task):
        # Handle cases where task might be None or not a Task object (e.g., in partial contexts)
        return {}
        
    task_dict = task.__dict__.copy()
    # Convert Enum members to their values for JSON serialization
    if 'status' in task_dict and hasattr(task_dict['status'], 'value'):
        task_dict['status'] = task_dict['status'].value
    if 'type' in task_dict and hasattr(task_dict['type'], 'value'):
        task_dict['type'] = task_dict['type'].value
    return task_dict

def parse_llm_response_to_json(llm_response_str: str) -> Optional[Dict[str, Any]]:
    """
    Parses a JSON string from the LLM response into a Python dictionary.
    Handles potential JSON decoding errors.
    """
    try:
        # Attempt to find JSON within a markdown code block
        match = re.search(r"```json\s*(.*?)\s*```", llm_response_str, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            json_str = llm_response_str # Assume the whole string is JSON if no markdown block found

        json_output = json.loads(json_str)
        return json_output
    except Exception as e:
        return e 