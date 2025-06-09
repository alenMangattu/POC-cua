import json
from typing import Dict, List, Any, Optional

from src.agent.llm import LLM
from src.agent.screen import VM
from src.agent.prompt_j2_management import get_planner_prompt, get_executer_prompt, get_implementation_planner_prompt
from src.agent.task_models import Task, TaskStatus, TaskType
from src.agent.execution_management import ExecutionContext
from src.agent.primitive_executor import PrimitiveExecutor
from src.utils import task_to_json_dict, parse_llm_response_to_json

class TaskExecutor:
    def __init__(self, vm: VM, execution_context: ExecutionContext, primitive_executor: PrimitiveExecutor, user_task: str):
        self.vm = vm
        self.execution_context = execution_context
        self.primitive_executor = primitive_executor
        self.user_task = user_task

    def execute_task_dfs(self, task: Task, current_level_tasks: List[Task]) -> None:
        print(f"Executing task: {task.id} - {task.description} (Depth: {task.depth}, Type: {task.type.value})")
        task.status = TaskStatus.IN_PROGRESS

        current_task_index = -1
        for i, t in enumerate(current_level_tasks):
            if t.id == task.id:
                current_task_index = i
                break

        preceding_siblings = []
        if current_task_index > 0:
            preceding_siblings.append(current_level_tasks[current_task_index - 1])
        if current_task_index > 1:
            preceding_siblings.append(current_level_tasks[current_task_index - 2])

        succeeding_siblings = []
        if current_task_index < len(current_level_tasks) - 1:
            succeeding_siblings.append(current_level_tasks[current_task_index + 1])
        if current_task_index < len(current_level_tasks) - 2:
            succeeding_siblings.append(current_level_tasks[current_task_index + 2])

        parent_task = self.execution_context.completed_tasks.get(task.parent_id) if task.parent_id else None

        formatted_context = f"""
End Goal / User Prompt: {self.user_task}

Current Task that needs to be executed:
ID: {task.id}
Description: {task.description}
Type: {task.type.value}
Status: {task.status.value}
Inputs: {task.inputs}
Outputs: {task.outputs}
Depends On: {task.depends_on}
Parent ID: {task.parent_id}
Depth: {task.depth}

Preceding Siblings (up to 2):
{json.dumps([task_to_json_dict(t) for t in preceding_siblings], indent=2) if preceding_siblings else "None"}

Succeeding Siblings (up to 2):
{json.dumps([task_to_json_dict(t) for t in succeeding_siblings], indent=2) if succeeding_siblings else "None"}

Parent Task:
{json.dumps(task_to_json_dict(parent_task), indent=2) if parent_task else "None"}
"""
        print(f"Formatted context for LLM:{formatted_context}")


        if task.type == TaskType.COMPOUND:
            print(f"Task {task.id} is COMPOUND. Decomposing...")
            wmctrlinfo = self.vm.get_wmctrl_info()
            planner_prompt = get_planner_prompt({"wmctrlinfo": wmctrlinfo})
            llm_response = LLM.run(planner_prompt, formatted_context, force_json_output=True)
            parsed_response = parse_llm_response_to_json(llm_response)

            if isinstance(parsed_response, Exception):
                task.status = TaskStatus.FAILED
                task.error_message = str(parsed_response)
                print(f"Error parsing LLM response for compound task decomposition: {parsed_response}")
                self.execution_context.completed_tasks[task.id] = task
                return

            sub_dag_raw = parsed_response.get("dag", [])
            subtasks = []
            for sub_task_data in sub_dag_raw:
                try:
                    sub_task_data['type'] = TaskType(sub_task_data['type'])
                    sub_task = Task(**sub_task_data)
                    sub_task.parent_id = task.id
                    sub_task.depth = task.depth + 1
                    subtasks.append(sub_task)
                except Exception as e:
                    print(f"Error creating subtask from dict: {sub_task_data} - {e}")

            if not subtasks:
                print(f"No subtasks generated for compound task {task.id}. Marking as completed/skipped.")
                task.status = TaskStatus.COMPLETED
                self.execution_context.completed_tasks[task.id] = task
                return

            for subtask in subtasks:
                self.execute_task_dfs(subtask, subtasks)

            task.status = TaskStatus.COMPLETED

        elif task.type == TaskType.PRIMITIVE:
            print(f"Task {task.id} is PRIMITIVE. Executing...")
            executer_prompt = get_executer_prompt({"wmctrlinfo": self.vm.get_wmctrl_info()})
            llm_response = LLM.run(executer_prompt, formatted_context, force_json_output=True)
            parsed_response = parse_llm_response_to_json(llm_response)

            if isinstance(parsed_response, Exception):
                task.status = TaskStatus.FAILED
                task.error_message = str(parsed_response)
                print(f"Error parsing LLM response for primitive task execution: {parsed_response}")
                self.execution_context.completed_tasks[task.id] = task
                return

            task.result = parsed_response
            task.status = TaskStatus.COMPLETED
            print(f"Primitive task {task.id} completed with result: {task.result}")

        elif task.type == TaskType.IMPLEMENTATION:
            print(f"Task {task.id} is IMPLEMENTATION. Decomposing into primitive steps...")
            implementation_planner_prompt = get_implementation_planner_prompt({
                "wmctrlinfo": self.vm.get_wmctrl_info(),
                "task": task_to_json_dict(task),
                "available_outputs": self.execution_context.available_outputs,
                "current_screen_state": self.execution_context.current_screen_state
            })
            llm_response = LLM.run(implementation_planner_prompt, "Generate a detailed plan of primitive steps for this implementation task, including success indicators and error recovery.", force_json_output=True)
            parsed_response = parse_llm_response_to_json(llm_response)

            print(f"Parsed response for implementation task {task.id}: {parsed_response}")
            if isinstance(parsed_response, Exception):
                task.status = TaskStatus.FAILED
                task.error_message = str(parsed_response)
                print(f"Error parsing LLM response for implementation task decomposition: {parsed_response}")
                self.execution_context.completed_tasks[task.id] = task
                return

            primitive_steps = parsed_response.get("steps", [])
            if not primitive_steps:
                print(f"No primitive steps generated for implementation task {task.id}. Marking as completed/skipped.")
                task.status = TaskStatus.COMPLETED
                self.execution_context.completed_tasks[task.id] = task
                return

            print(f"Generated primitive steps for {task.id}: {json.dumps(primitive_steps, indent=2)}")
            
            all_primitive_steps_successful = True
            for p_step in primitive_steps:
                if not self.primitive_executor.execute_primitive_step(p_step):
                    all_primitive_steps_successful = False
                    print(f"Primitive step failed: {p_step.get('step_id')}. Stopping implementation task execution.")
                    break

            if all_primitive_steps_successful:
                print(f"All primitive steps for task {task.id} completed successfully.")
                final_validation_indicators = parsed_response.get("final_validation", [])
                if final_validation_indicators:
                    print(f"Performing final validation for task {task.id}...")
                    if self.primitive_executor.success_checker.check_indicators(final_validation_indicators):
                        print(f"Final validation for task {task.id} successful.")
                        task.status = TaskStatus.COMPLETED
                    else:
                        print(f"Final validation for task {task.id} failed.")
                        task.status = TaskStatus.FAILED
                        task.error_message = "Final validation checks failed."
                else:
                    print(f"No final validation steps defined for task {task.id}. Marking as completed.")
                    task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "One or more primitive steps failed and could not be recovered."

        else:
            print(f"Unknown task type: {task.type}. Skipping task {task.id}.")
            task.status = TaskStatus.SKIPPED

        self.execution_context.completed_tasks[task.id] = task 