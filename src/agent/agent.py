import json
import os
import re
import time
from typing import Dict, List, Any, Optional, Tuple

from src.agent.llm import LLM
from src.agent.screen import VM
from src.agent.prompt_j2_management import get_planner_prompt, get_executer_prompt, get_implementation_planner_prompt
from src.agent.task_models import Task, TaskStatus, TaskType
from src.agent.execution_management import ExecutionContext, TaskStack
from src.utils import task_to_json_dict, parse_llm_response_to_json
from src.agent.success_checker import SuccessChecker
from src.agent.primitive_executor import PrimitiveExecutor
from src.agent.task_executor import TaskExecutor

class GeneralPurposeAgent:
    def __init__(self, vm: VM):
        self.vm = vm
        self.task_stack = TaskStack()
        self.execution_context = ExecutionContext()
        self.success_checker = SuccessChecker(vm, self.execution_context)
        self.primitive_executor = PrimitiveExecutor(vm, self.execution_context, self.success_checker)
        self.user_task = "" 
        self.task_executor = TaskExecutor(vm, self.execution_context, self.primitive_executor, self.user_task)

    def run(self, initial_dag_data: List[Dict[str, Any]], user_task_description: str) -> Dict[str, Any]:
        """
        Executes a given DAG of tasks using a Depth-First Search approach,
        handling compound task decomposition recursively.
        """
        self.user_task = user_task_description
        self.task_executor.user_task = user_task_description

        initial_tasks = []
        for task_data in initial_dag_data:
            try:
                task_data['type'] = TaskType(task_data['type'])
                initial_tasks.append(Task(**task_data))
            except Exception as e:
                print(f"Error creating initial task from dict: {task_data} - {e}")

        for task in initial_tasks:
            self.task_executor.execute_task_dfs(task, initial_tasks)

        print("DFS execution completed.")
        return {"completed_tasks": {k: v.__dict__ for k, v in self.execution_context.completed_tasks.items()}} 