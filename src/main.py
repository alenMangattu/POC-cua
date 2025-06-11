import types
from src.agent.llm import LLM
from src.agent.screen import VM
from src.agent.prompt_j2_management import get_planner_prompt
import os
from src.agent.agent import GeneralPurposeAgent
from src.agent.tasks.task_models import TaskType
from src.utils import parse_llm_response_to_json
from google.genai import types as genai_types

def main():
    # Initialize VM
    vm_server_ip = os.getenv("VM_SERVER_IP", "192.168.1.64")
    vm_server_port = int(os.getenv("VM_SERVER_PORT", "6969"))
    vm = VM(vm_server_ip=vm_server_ip, vm_server_port=vm_server_port)

    # Initialize LLM
    LLM.initialize()

    # Create agents
    agent = GeneralPurposeAgent(vm)
    
    # Example tasks
    user_task = "Goto mrbeast's youtube channel and comment"
    wmctrlinfo = vm.get_wmctrl_info()
    # wmctrlinfo = {}
    prompt = get_planner_prompt({"wmctrlinfo": wmctrlinfo})
    response = LLM.run(prompt, user_task, force_json_output=True, config=genai_types.GenerateContentConfig(
        temperature=0.7,
        max_output_tokens=8192,
        candidate_count=1,
        top_p=0.95
    ))
    
    parsed_response = parse_llm_response_to_json(response)
    # print(parsed_response)
    # exit()
    if isinstance(parsed_response, Exception):
        print(f"Error parsing LLm response: {parsed_response}")
        return
   
    initial_dag = [task for task in parsed_response.get("dag", []) if task.get("type") != "human"]

    # Remove 'human_method' from each task in initial_dag if it exists
    for task in initial_dag:
        if "human_method" in task:
            del task["human_method"]

    print(initial_dag)
    if initial_dag:
        for task_data in initial_dag:
            if 'type' in task_data and isinstance(task_data['type'], str):
                print(task_data['type'])
                task_data['type'] = TaskType(task_data['type'])
   
    # exit() 
    result = agent.run(initial_dag, user_task)
    print("Final execution result:", result)

if __name__ == "__main__":
    main()