from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from src.agent.tasks.task_models import Task # Import Task

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