from src.agent.llm import LLM
from src.agent.screen import VM
from src.agent.prompt_j2_management import get_planner_prompt
import json
import os


def main():
    # Initialize VM with default server IP and port, or from environment variables
    vm_server_ip = os.getenv("VM_SERVER_IP", "192.168.1.64")
    vm_server_port = int(os.getenv("VM_SERVER_PORT", "6969"))
    vm = VM(vm_server_ip=vm_server_ip, vm_server_port=vm_server_port)

    # Initialize LLM
    LLM.initialize()

    # print(LLM.run("HI", "world"))
    user_task = "goto my website https://axelot.com and tell me how is the seo" # The overall goal

    wmctrlinfo = vm.get_wmctrl_info()
    print(f"WMCTRL info: {wmctrlinfo}")
    planner_prompt = get_planner_prompt(context={
        "wmctrlinfo": wmctrlinfo,
    })
    print(f"Planner prompt (system_prompt): {planner_prompt}")
    print(f"User task (user_prompt): {user_task}")
    response = LLM.run(planner_prompt, user_task, force_json_output=True)
    print(response)


if __name__ == "__main__":
    main()
