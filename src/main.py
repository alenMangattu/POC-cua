from src.agent.llm import LLM
from src.agent.screen import VM
from src.agent.prompt_j2_management import get_planner_prompt
import os
from src.agent.agent import GeneralPurposeAgent
from src.agent.task_models import TaskType
from src.utils import parse_llm_response_to_json

def main():
    # Initialize VM
    vm_server_ip = os.getenv("VM_SERVER_IP", "192.168.1.64")
    vm_server_port = int(os.getenv("VM_SERVER_PORT", "6969"))
    vm = VM(vm_server_ip=vm_server_ip, vm_server_port=vm_server_port)

    # Initialize LLM
    LLM.initialize()

    # Create agent
    agent = GeneralPurposeAgent(vm)
    
    # Example tasks
    user_task = "Open firefox"
    wmctrlinfo = vm.get_wmctrl_info()
    prompt = get_planner_prompt({"wmctrlinfo": wmctrlinfo})
    response = LLM.run(prompt, user_task, force_json_output=True)
    
    parsed_response = parse_llm_response_to_json(response)

    if isinstance(parsed_response, Exception):
        print(f"Error parsing LLm response: {parsed_response}")
        return
   
    initial_dag = parsed_response.get("dag")

    if initial_dag:
        for task_data in initial_dag:
            if 'type' in task_data and isinstance(task_data['type'], str):
                task_data['type'] = TaskType(task_data['type'])

    result = agent.run(initial_dag, user_task)
    print("Final execution result:", result)

if __name__ == "__main__":
    main()