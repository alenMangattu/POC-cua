from llm import LLM
from jinja2 import Template, Environment, FileSystemLoader
from google.genai import types
import json

from screen import VM
from prompt_j2_management import analyse_genesis_classification

prompt_sys_genesis_classification = analyse_genesis_classification()
user_input = input("Enter a task: ")
response = LLM.run(
    prompt_sys_genesis_classification,
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
        vm = VM(omniparser_url="https://microsoft-omniparser-v2.hf.space")
        success, ui_class, ui_elements = vm.analyze_screenshot()
        if success:
            print(f"Found {len(ui_elements)} UI elements")
            
            context = {
                "scan": True,
                "ui_screen": ui_elements,
            }
            print("--------------------------------")
            print(context)
            print("--------------------------------")
            prompt_user_genesis_classification = analyse_genesis_classification(context)
            print("--------------------------------")
            print(prompt_user_genesis_classification)
            print("--------------------------------")
            second_response = LLM.run(
                prompt_user_genesis_classification,
                user_input,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    candidate_count=1,
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                )
            )
            
            # Parse and handle the second response
            second_response_data = json.loads(second_response)
            print("\nSecond classification after screen analysis:")
            print(second_response)
            
            # Handle the second classification
            if second_response_data["classification"] == "HTN":
                print("Processing as HTN task")
                # Add HTN handling here
            elif second_response_data["classification"] == "SIMPLE":
                print("Processing as SIMPLE task")
                # Add SIMPLE task handling here
            elif second_response_data["classification"] == "REFUSED":
                print(f"Task refused: {second_response_data.get('reason', 'No reason provided')}")
            elif second_response_data["classification"] == "CONVERSATIONAL":
                print(second_response_data.get("response", "No response provided"))
            
            prompt_user_genesis_classification2 = analyse_genesis_classification(context)
            print(LLM.run(prompt_user_genesis_classification2, user_input + "What do you understand about this screen what os is it be precise, so give me conversational response ?", config=types.GenerateContentConfig(
                temperature=0.1,
                candidate_count=1,
                max_output_tokens=2048,
                response_mime_type="application/json"
            )))
        else:
            print("Screen analysis failed")
           
 
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