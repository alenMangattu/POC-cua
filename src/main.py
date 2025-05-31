from llm import LLM
from jinja2 import Template, Environment, FileSystemLoader
from google.genai import types
import json

env = Environment(loader=FileSystemLoader(searchpath="./templates"))
template = env.get_template("sys_gensis_classification.j2")

LLM.initialize()

user_input = input("Enter a task: ")
response = LLM.run(
    template.render(),
    user_input,
    config=types.GenerateContentConfig(
        temperature=0.1,
        candidate_count=1,
        max_output_tokens=2048,
        response_mime_type="application/json"
    )
)

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