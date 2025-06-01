from llm import LLM
from jinja2 import Template, Environment, FileSystemLoader
from google.genai import types
import json

from screen import VM
from prompt_headers import analyse_genesis_classification

prompt_headers = analyse_genesis_classification(3)
user_input = input("Enter a task: ")
response = LLM.run(
    prompt_headers,
    user_input,
    config=types.GenerateContentConfig(
        temperature=0.1,
        candidate_count=1,
        max_output_tokens=2048,
        response_mime_type="application/json"
    )
)

# vm = VM(omniparser_url="https://80c06c675c6a6462b5.gradio.live/")
# vm.analyze_screenshot()
try:
    response_data = json.loads(response)
    print(response)

    if response_data["classification"] == "SCAN":
        print("Screen analysis needed")
        # TODO: Screen analysis
        context = {
            "scan": True,
            "ui_screen": "ui_screen",
        }
    elif response_data["classification"] == "HTN":
        print("HTN")
    elif response_data["classification"] == "SIMPLE":
        print("SIMPLE")
    elif response_data["classification"] == "REFUSED":
        print("REFUSED")
    elif response_data["classification"] == "CONVERSATIONAL":
        print(response_data["response"])
except json.JSONDecodeError:
    print("Error: Could not parse JSON response")
    print("Raw response:", response)
except KeyError as e:
    print(f"Error: Missing expected key in response: {e}")
    print("Raw response:", response)