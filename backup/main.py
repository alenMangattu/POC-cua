from src.agent.llm import LLM
from src.agent.screen import VM
from src.agent.prompt_j2_management import get_planner_prompt, get_executer_prompt
import json
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import time
import traceback

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DECOMPOSED = "decomposed"

class TaskType(Enum):
    PRIMITIVE = "primitive"
    COMPOUND = "compound"
    VALIDATION = "validation"
    INFORMATION_GATHERING = "information_gathering"

@dataclass
class Task:
    id: str
    description: str
    type: str
    status: TaskStatus = TaskStatus.PENDING
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    depth: int = 0
    retry_count: int = 0
    error_message: Optional[str] = None
    result: Optional[Any] = None
    validation_criteria: List[str] = field(default_factory=list)

@dataclass
class ExecutionContext:
    """Maintains global execution state"""
    completed_tasks: Dict[str, Task] = field(default_factory=dict)
    available_outputs: Dict[str, Any] = field(default_factory=dict)
    current_screen_state: Optional[str] = None
    wmctrl_info: Optional[Dict] = None
    last_error: Optional[str] = None
    
class TaskStack:
    """Stack-based task management for subroutine-like execution"""
    
    def __init__(self):
        self._stack: List[Task] = []
        self._execution_history: List[Task] = []
        
    def push(self, task: Task) -> None:
        """Push task onto stack"""
        self._stack.append(task)
        
    def pop(self) -> Optional[Task]:
        """Pop task from stack"""
        if self._stack:
            task = self._stack.pop()
            self._execution_history.append(task)
            return task
        return None
        
    def peek(self) -> Optional[Task]:
        """Peek at top task without removing"""
        return self._stack[-1] if self._stack else None
        
    def is_empty(self) -> bool:
        """Check if stack is empty"""
        return len(self._stack) == 0
        
    def push_subtasks(self, subtasks: List[Task], parent_task: Task) -> None:
        """Push subtasks in reverse order so they execute in correct order"""
        for subtask in reversed(subtasks):
            subtask.parent_id = parent_task.id
            subtask.depth = parent_task.depth + 1
            self.push(subtask)
            
    def get_depth(self) -> int:
        """Get current stack depth"""
        return len(self._stack)
        
    def clear_children_of(self, parent_id: str) -> None:
        """Remove all tasks that are children of given parent"""
        self._stack = [t for t in self._stack if t.parent_id != parent_id]

class GeneralPurposeAgent:
    def __init__(self, vm: VM, max_iterations: int = 100, max_depth: int = 10):
        self.vm = vm
        self.llm = LLM
        self.max_iterations = max_iterations
        self.max_depth = max_depth
        self.task_stack = TaskStack()
        self.context = ExecutionContext()
        self.iteration_count = 0
        
    def run(self, user_task: str) -> Dict[str, Any]:
        """Main entry point for task execution"""
        print(f"\n🎯 Starting task: {user_task}")
        
        # Phase 1: Planning
        plan = self._create_plan(user_task)
        if not plan:
            return {"success": False, "error": "Failed to create plan"}
            
        # Phase 2: Initialize task stack with DAG tasks
        self._initialize_task_stack(plan)
        
        # Phase 3: Execute tasks from stack
        while not self.task_stack.is_empty() and self.iteration_count < self.max_iterations:
            self.iteration_count += 1
            
            # Get next task
            current_task = self.task_stack.pop()
            if not current_task:
                continue
                
            print(f"\n📋 Iteration {self.iteration_count}: Processing task '{current_task.id}' (depth: {current_task.depth})")
            
            # Check dependencies
            if not self._check_dependencies(current_task):
                print(f"⏸️  Task blocked on dependencies")
                current_task.status = TaskStatus.BLOCKED
                self.task_stack.push(current_task)  # Re-add to stack
                continue
                
            # Execute task
            try:
                result = self._execute_task(current_task)
                
                # Handle execution result
                if result['status'] == 'completed':
                    self._handle_task_completion(current_task, result)
                elif result['status'] == 'decomposed':
                    self._handle_task_decomposition(current_task, result)
                elif result['status'] == 'failed':
                    self._handle_task_failure(current_task, result)
                    
            except Exception as e:
                print(f"❌ Error executing task: {e}")
                traceback.print_exc()
                self._handle_task_failure(current_task, {"error": str(e)})
                
        # Phase 4: Generate final report
        return self._generate_final_report()
        
    def _create_plan(self, user_task: str) -> Optional[Dict]:
        """Use planner to create initial plan"""
        print("\n🤔 Creating plan...")
        
        # Get current window state
        self.context.wmctrl_info = self.vm.get_wmctrl_info()
        
        # Generate plan
        planner_prompt = get_planner_prompt(context={
            "wmctrlinfo": self.context.wmctrl_info
        })
        
        response = self.llm.run(planner_prompt, user_task, force_json_output=True)
        
        try:
            plan = json.loads(response)
            print(f"✅ Plan created with {len(plan.get('dag', []))} tasks")
            return plan
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse plan: {e}")
            return None
            
    def _initialize_task_stack(self, plan: Dict) -> None:
        """Initialize task stack from plan DAG"""
        dag = plan.get('dag', [])
        
        # Convert DAG tasks to Task objects
        tasks_by_id = {}
        for task_data in dag:
            task = Task(
                id=task_data['id'],
                description=task_data['description'],
                type=task_data['type'],
                inputs=task_data.get('inputs', []),
                outputs=task_data.get('outputs', []),
                depends_on=task_data.get('depends_on', []),
                validation_criteria=task_data.get('validation_criteria', [])
            )
            tasks_by_id[task.id] = task

        # Push tasks in reverse critical path order
        # This ensures that tasks with no dependencies or fulfilled dependencies are popped first
        critical_path = plan.get('execution_strategy', {}).get('critical_path', [])
        for task_id in reversed(critical_path):
            if task_id in tasks_by_id:
                self.task_stack.push(tasks_by_id[task_id])
            
    def _check_dependencies(self, task: Task) -> bool:
        """Check if all task dependencies are satisfied"""
        for dep_id in task.depends_on:
            if dep_id not in self.context.completed_tasks:
                return False
            if self.context.completed_tasks[dep_id].status != TaskStatus.COMPLETED:
                return False
        return True
        
    def _execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a single task using the executer"""
        print(f"🔧 Executing: {task.description}")
        
        # Update window state
        self.context.wmctrl_info = self.vm.get_wmctrl_info()
        
        # Prepare task for executer
        task_json = {
            "id": task.id,
            "description": task.description,
            "type": task.type,
            "inputs": task.inputs,
            "outputs": task.outputs,
            "validation_criteria": task.validation_criteria
        }
        
        # Get executer response
        executer_prompt = get_executer_prompt(context={
            "wmctrlinfo": self.context.wmctrl_info
        })
        
        response = self.llm.run(
            executer_prompt, 
            json.dumps(task_json), 
            force_json_output=True
        )
        
        try:
            executer_response = json.loads(response)
            return self._process_executer_response(task, executer_response)
        except json.JSONDecodeError as e:
            return {"status": "failed", "error": f"Failed to parse executer response: {e}"}
            
    def _process_executer_response(self, task: Task, response: Dict) -> Dict[str, Any]:
        """Process response from executer and take appropriate action"""
        classification = response.get("classification")
        
        if classification == "EXECUTE_PRIMITIVE":
            return self._execute_primitive_action(task, response)
        elif classification == "DECOMPOSE_TASK":
            return self._decompose_task(task, response)
        elif classification == "GATHER_INFORMATION":
            return self._gather_information(task, response)
        elif classification == "ERROR_RECOVERY":
            return self._handle_error_recovery(task, response)
        elif classification == "STATE_CLARIFICATION":
            return self._clarify_state(task, response)
        else:
            return {"status": "failed", "error": f"Unknown classification: {classification}"}
            
    def _execute_primitive_action(self, task: Task, response: Dict) -> Dict[str, Any]:
        """Execute a primitive VM action"""
        action_details = response.get("action", {})
        action_type = action_details.get("type")
        
        if action_type == "VM_TOOLS":
            # Execute VM operations
            operations = action_details.get("details", {}).get("operations", [])
            results = self.vm.run_operations(operations)
            
            # Check if all operations succeeded
            all_success = all(r.get("success", False) for r in results)
            
            # Perform validation if specified
            validation_required = response.get("validation_required")
            if validation_required and all_success:
                validation_result = self._perform_validation(validation_required)
                if not validation_result["success"]:
                    return {"status": "failed", "error": "Validation failed", "details": validation_result}
            
            return {
                "status": "completed" if all_success else "failed",
                "results": results
            }
            
        elif action_type == "SCAN":
            # Execute scan
            scan_details = action_details.get("details", {})
            scan_result = self.vm.scan_screen(
                method=scan_details.get("method", "Omni Parser"),
                area_type=scan_details.get("area", {}).get("type", "full"),
                coordinates=scan_details.get("area", {}).get("coordinates", []),
                window_id=scan_details.get("area", {}).get("window_id", ""),
                vision_model_query=scan_details.get("vision_model_query", "")
            )
            # Store screen state
            if scan_result.get("success"):
                self.context.current_screen_state = scan_result
            return {
                "status": "completed" if scan_result.get("success") else "failed",
                "scan_result": scan_result
            }
        else:
            return {"status": "failed", "error": f"Unknown action type: {action_type}"}
            
    def _decompose_task(self, task: Task, response: Dict) -> Dict[str, Any]:
        """Decompose a compound task into subtasks"""
        decomposition = response.get("decomposition", {})
        subtasks_data = decomposition.get("subtasks", [])
        
        if not subtasks_data:
            return {"status": "failed", "error": "No subtasks provided"}
            
        # Check depth limit
        if task.depth >= self.max_depth:
            return {"status": "failed", "error": f"Maximum decomposition depth ({self.max_depth}) reached"}
            
        # Create subtask objects
        subtasks = []
        for subtask_data in subtasks_data:
            subtask = Task(
                id=f"{task.id}_{subtask_data['id']}",
                description=subtask_data['description'],
                type=subtask_data['type'],
                inputs=subtask_data.get('inputs', []),
                outputs=subtask_data.get('outputs', []),
                depends_on=[f"{task.id}_{dep}" for dep in subtask_data.get('depends_on', [])],
                validation_criteria=[subtask_data.get('validation', '')]
            )
            subtasks.append(subtask)
            
        # Push subtasks to stack
        self.task_stack.push_subtasks(subtasks, task)
        
        return {"status": "decomposed", "subtask_count": len(subtasks)}
        
    def _gather_information(self, task: Task, response: Dict) -> Dict[str, Any]:
        """Gather information using SCAN"""
        observation_method = response.get("observation_method", "SCAN")
        
        if observation_method == "SCAN":
            # Use Omni Parser for UI element detection
            scan_result = self.vm.scan_screen(
                method="Omni Parser",
                area_type="full",
                coordinates=[],
                window_id="",
                vision_model_query=""
            )
            
            self.context.current_screen_state = scan_result
            
            return {
                "status": "completed",
                "information": scan_result
            }
        else:
            return {"status": "failed", "error": f"Unknown observation method: {observation_method}"}
            
    def _perform_validation(self, validation_config: Dict) -> Dict[str, Any]:
        """Use Vision Model for validation"""
        check_for = validation_config.get("check_for", "")
        timeout = validation_config.get("timeout", 3000)
        
        # Wait a bit for UI to update
        time.sleep(0.5)
        
        # Use Vision Model to check for expected state
        validation_result = self.vm.scan_screen(
            method="Vision Model",
            area_type="full",
            coordinates=[],
            window_id="",
            vision_model_query=f"Check if: {check_for}. Respond with 'yes' if true, 'no' if false."
        )
        
        if validation_result.get("success"):
            vision_response = validation_result.get("vision_analysis", "").lower()
            success = "yes" in vision_response
            return {
                "success": success,
                "details": vision_response
            }
        else:
            return {
                "success": False,
                "details": "Validation scan failed"
            }
            
    def _handle_error_recovery(self, task: Task, response: Dict) -> Dict[str, Any]:
        """Handle error recovery strategy"""
        recovery_strategy = response.get("recovery_strategy", [])
        
        for step in recovery_strategy:
            step_action = step.get("action", "")
            
            if "SCAN" in step_action:
                # Perform a scan to understand current state
                scan_result = self.vm.scan_screen(
                    method="Omni Parser + Vision Model",
                    area_type="full",
                    coordinates=[],
                    window_id="",
                    vision_model_query="What is the current state of the screen? Are there any error messages?"
                )
                self.context.current_screen_state = scan_result
                
            elif "retry" in step_action.lower():
                # Retry the task
                task.retry_count += 1
                if task.retry_count < 3:
                    self.task_stack.push(task)  # Re-add to stack
                    return {"status": "retry", "retry_count": task.retry_count}
                    
        return {"status": "failed", "error": "Error recovery exhausted"}
        
    def _clarify_state(self, task: Task, response: Dict) -> Dict[str, Any]:
        """Clarify uncertain state"""
        clarification_needed = response.get("clarification_needed", {})
        specific_query = clarification_needed.get("specific_query", "")
        
        # Use Vision Model for clarification
        clarification_result = self.vm.scan_screen(
            method="Vision Model",
            area_type="full",
            coordinates=[],
            window_id="",
            vision_model_query=specific_query
        )
        
        # Based on clarification, decide next action
        decision_tree = clarification_needed.get("decision_tree", {})
        vision_response = clarification_result.get("vision_analysis", "").lower()
        
        # Simple decision logic
        if any(keyword in vision_response for keyword in ["found", "exists", "yes", "present"]):
            next_action = decision_tree.get("if_found", "continue")
        else:
            next_action = decision_tree.get("if_not_found", "skip")
            
        if next_action == "skip":
            return {"status": "completed", "action": "skipped due to state"}
        else:
            # Re-add task for execution with clarified state
            self.task_stack.push(task)
            return {"status": "retry", "clarification": vision_response}
            
    def _handle_task_completion(self, task: Task, result: Dict) -> None:
        """Handle successful task completion"""
        task.status = TaskStatus.COMPLETED
        task.result = result
        self.context.completed_tasks[task.id] = task
        
        # Store outputs for dependent tasks
        for output in task.outputs:
            self.context.available_outputs[output] = result
            
        print(f"✅ Task completed: {task.id}")
        
    def _handle_task_decomposition(self, task: Task, result: Dict) -> None:
        """Handle task decomposition"""
        task.status = TaskStatus.DECOMPOSED
        self.context.completed_tasks[task.id] = task
        print(f"🔄 Task decomposed into {result.get('subtask_count', 0)} subtasks")
        
    def _handle_task_failure(self, task: Task, result: Dict) -> None:
        """Handle task failure with recovery attempts"""
        error_msg = result.get("error", "Unknown error")
        task.error_message = error_msg
        
        print(f"❌ Task failed: {error_msg}")
        
        # Retry logic
        task.retry_count += 1
        if task.retry_count < 3:
            print(f"🔄 Retrying task (attempt {task.retry_count + 1}/3)")
            time.sleep(2 ** task.retry_count)  # Exponential backoff
            self.task_stack.push(task)
        else:
            task.status = TaskStatus.FAILED
            self.context.completed_tasks[task.id] = task
            
            # Clear any dependent tasks
            self.task_stack.clear_children_of(task.id)
            
    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive execution report"""
        completed_count = sum(1 for t in self.context.completed_tasks.values() 
                            if t.status == TaskStatus.COMPLETED)
        failed_count = sum(1 for t in self.context.completed_tasks.values() 
                         if t.status == TaskStatus.FAILED)
        
        return {
            "success": failed_count == 0 and self.task_stack.is_empty(),
            "iterations": self.iteration_count,
            "completed_tasks": completed_count,
            "failed_tasks": failed_count,
            "remaining_tasks": self.task_stack.get_depth(),
            "task_details": {
                task_id: {
                    "status": task.status.value,
                    "description": task.description,
                    "error": task.error_message,
                    "retry_count": task.retry_count
                }
                for task_id, task in self.context.completed_tasks.items()
            }
        }


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
    # user_task = "Open Firefox and navigate to YouTube"
    # user_task = "Find the weather forecast for tomorrow"
    user_task = "Go to the YouTube channel of Reda Marzouk and write a comment saying 'Great content!'"
    
    # Run the task
    result = agent.run(user_task)
    
    # Print final report
    print("\n" + "="*60)
    print("📊 EXECUTION REPORT")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Total iterations: {result['iterations']}")
    print(f"Completed tasks: {result['completed_tasks']}")
    print(f"Failed tasks: {result['failed_tasks']}")
    print(f"Remaining tasks: {result['remaining_tasks']}")
    
    if result['failed_tasks'] > 0:
        print("\n❌ Failed Tasks:")
        for task_id, details in result['task_details'].items():
            if details['status'] == 'failed':
                print(f"  - {task_id}: {details['description']}")
                print(f"    Error: {details['error']}")
                print(f"    Retries: {details['retry_count']}")


if __name__ == "__main__":
    main()
