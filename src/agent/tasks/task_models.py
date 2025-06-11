from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Any

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
    ANALYSIS = "analysis"
    RESEARCH = "research"
    IMPLEMENTATION = "implementation"
    COORDINATION = "coordination"

@dataclass
class Task:
    id: str
    description: str
    type: TaskType
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
    estimated_time: Optional[str] = None
    complexity: Optional[str] = None
    tools_needed: List[str] = field(default_factory=list)
    vision_model_query: Optional[str] = None