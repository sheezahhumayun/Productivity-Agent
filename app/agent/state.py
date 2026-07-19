from dataclasses import dataclass, field
from typing import Optional, List, Any
import uuid


@dataclass
class ToolCallRecord:
    step: int
    tool_name: str
    tool_id: str
    tool_input: dict
    tool_result: Optional[dict] = None
    approved: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class PendingApproval:
    """Stores the mid-run state when an approval-required tool is encountered."""
    run_id: str
    log_id: int
    tool_use_id: str
    tool_name: str
    tool_input: dict
    messages: List[dict]  # messages up to and including the assistant's tool_use block
    step_count: int
    tool_calls_log: List[ToolCallRecord]
    human_description: str  # what the tool will do in plain English


@dataclass
class AgentRunResult:
    run_id: str
    response_text: Optional[str] = None
    pending_approval: Optional[PendingApproval] = None
    error: Optional[str] = None
    step_count: int = 0
    tools_called: List[ToolCallRecord] = field(default_factory=list)

    @property
    def needs_approval(self) -> bool:
        return self.pending_approval is not None

    @property
    def is_complete(self) -> bool:
        return self.response_text is not None or self.error is not None


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:8]}"
