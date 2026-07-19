from app.tools.task_tools import TASK_TOOL_DEFS, execute_task_tool
from app.tools.note_tools import NOTE_TOOL_DEFS, execute_note_tool
from app.tools.planning_tools import PLANNING_TOOL_DEFS, execute_planning_tool


def _to_openai_format(tool_defs: list) -> list:
    """Convert {name, description, input_schema} → OpenAI function tool format."""
    result = []
    for t in tool_defs:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })
    return result


ALL_TOOL_DEFS = (
    _to_openai_format(TASK_TOOL_DEFS)
    + _to_openai_format(NOTE_TOOL_DEFS)
    + _to_openai_format(PLANNING_TOOL_DEFS)
)

_ROUTERS = {
    **{t["name"]: execute_task_tool for t in TASK_TOOL_DEFS},
    **{t["name"]: execute_note_tool for t in NOTE_TOOL_DEFS},
    **{t["name"]: execute_planning_tool for t in PLANNING_TOOL_DEFS},
}


def execute_tool(name: str, tool_input: dict) -> dict:
    router = _ROUTERS.get(name)
    if not router:
        return {"success": False, "error": f"Unknown tool: {name}"}
    try:
        return router(name, tool_input)
    except Exception as e:
        return {"success": False, "error": str(e)}
