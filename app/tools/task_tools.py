from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.database import repository as repo

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"pending", "in_progress", "blocked", "completed", "cancelled"}


class CreateTaskInput(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("priority")
    @classmethod
    def check_priority(cls, v):
        if v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {VALID_PRIORITIES}")
        return v


class ListTasksInput(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    due_before: Optional[str] = None
    tag: Optional[str] = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class UpdateTaskInput(BaseModel):
    task_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def check_priority(cls, v):
        if v and v not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {VALID_PRIORITIES}")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class CompleteTaskInput(BaseModel):
    task_id: int


class DeleteTaskInput(BaseModel):
    task_id: int


TASK_TOOL_DEFS = [
    {
        "name": "create_task",
        "description": (
            "Create a new task and save it to the database. "
            "Use this when the user wants to add a task, to-do item, or action item. "
            "REQUIRES human approval before execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short, clear task title"},
                "description": {"type": "string", "description": "Detailed description of what needs to be done"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Task priority level",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date in YYYY-MM-DD format",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags for categorization",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": (
            "Retrieve tasks from the database with optional filters. "
            "Use this to show pending tasks, filter by priority, status, or due date. "
            "Does NOT require approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "blocked", "completed", "cancelled"],
                    "description": "Filter by task status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Filter by priority",
                },
                "due_before": {
                    "type": "string",
                    "description": "Show tasks due before this date (YYYY-MM-DD)",
                },
                "tag": {
                    "type": "string",
                    "description": "Filter tasks that have this tag",
                },
            },
            "required": [],
        },
    },
    {
        "name": "update_task",
        "description": (
            "Update fields of an existing task. "
            "Use the task ID from list_tasks. "
            "REQUIRES human approval before execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "The ID of the task to update"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                },
                "due_date": {"type": "string", "description": "YYYY-MM-DD format"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "blocked", "completed", "cancelled"],
                },
                "tags": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string", "description": "Additional notes about this task"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "complete_task",
        "description": (
            "Mark a task as completed. "
            "REQUIRES human approval before execution. "
            "This action sets the task status to 'completed'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID of the task to complete"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": (
            "Permanently delete a task from the database. "
            "This action is IRREVERSIBLE. "
            "REQUIRES human approval before execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "ID of the task to delete"},
            },
            "required": ["task_id"],
        },
    },
]


def execute_task_tool(name: str, tool_input: dict) -> dict:
    if name == "create_task":
        inp = CreateTaskInput(**tool_input)
        task = repo.create_task(
            title=inp.title,
            description=inp.description,
            priority=inp.priority,
            due_date=inp.due_date,
            tags=inp.tags,
        )
        return {"success": True, "task": task, "message": f"Task #{task['id']} created: {task['title']}"}

    if name == "list_tasks":
        inp = ListTasksInput(**tool_input)
        tasks = repo.list_tasks(
            status=inp.status,
            priority=inp.priority,
            due_before=inp.due_before,
            tag=inp.tag,
        )
        return {"success": True, "tasks": tasks, "count": len(tasks)}

    if name == "update_task":
        inp = UpdateTaskInput(**tool_input)
        task = repo.update_task(
            task_id=inp.task_id,
            title=inp.title,
            description=inp.description,
            priority=inp.priority,
            due_date=inp.due_date,
            status=inp.status,
            tags=inp.tags,
            notes=inp.notes,
        )
        if not task:
            return {"success": False, "error": f"Task #{inp.task_id} not found"}
        return {"success": True, "task": task, "message": f"Task #{task['id']} updated"}

    if name == "complete_task":
        inp = CompleteTaskInput(**tool_input)
        task = repo.complete_task(inp.task_id)
        if not task:
            return {"success": False, "error": f"Task #{inp.task_id} not found"}
        return {"success": True, "task": task, "message": f"Task #{task['id']} marked as completed"}

    if name == "delete_task":
        inp = DeleteTaskInput(**tool_input)
        deleted = repo.delete_task(inp.task_id)
        if not deleted:
            return {"success": False, "error": f"Task #{inp.task_id} not found"}
        return {"success": True, "message": f"Task #{inp.task_id} permanently deleted"}

    return {"success": False, "error": f"Unknown task tool: {name}"}
