import json
import time
import logging
from datetime import datetime
from typing import Optional, List

from openai import OpenAI, APIConnectionError, AuthenticationError

from app.config import (
    API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    MAX_AGENT_STEPS,
    MAX_TOOL_RETRIES,
    APPROVAL_REQUIRED_TOOLS,
)
from app.agent.state import AgentRunResult, PendingApproval, ToolCallRecord, new_run_id
from app.agent.prompts import SYSTEM_PROMPT
from app.tools import ALL_TOOL_DEFS, execute_tool
from app.database import repository as repo

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=API_KEY, base_url=LLM_BASE_URL)
    return _client


def _human_description(tool_name: str, tool_input: dict) -> str:
    """Plain-English description of what the tool will do."""
    if tool_name == "create_task":
        return (
            f"Create task: **\"{tool_input.get('title', '?')}\"** "
            f"(priority: {tool_input.get('priority', 'medium')}"
            + (f", due: {tool_input['due_date']}" if tool_input.get("due_date") else "")
            + ")"
        )
    if tool_name == "update_task":
        changes = {k: v for k, v in tool_input.items() if k != "task_id" and v is not None}
        return f"Update Task #{tool_input.get('task_id', '?')}: {json.dumps(changes)}"
    if tool_name == "complete_task":
        task = repo.get_task(tool_input.get("task_id", 0))
        title = task["title"] if task else f"ID {tool_input.get('task_id', '?')}"
        return f"Mark task as **completed**: \"{title}\""
    if tool_name == "delete_task":
        task = repo.get_task(tool_input.get("task_id", 0))
        title = task["title"] if task else f"ID {tool_input.get('task_id', '?')}"
        return f"**Permanently delete** task: \"{title}\" (irreversible)"
    if tool_name == "save_note":
        return (
            f"Save note: **\"{tool_input.get('title', '?')}\"** "
            f"(category: {tool_input.get('category', 'none')})"
        )
    return f"Execute `{tool_name}` with {json.dumps(tool_input)}"


def _add_date_to_system() -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return SYSTEM_PROMPT + f"\n\nToday's date: {today}"


def _run_loop(
    messages: List[dict],
    run_id: str,
    log_id: int,
    step_count: int,
    tool_calls_log: List[ToolCallRecord],
    tool_retries: dict,
) -> AgentRunResult:
    """Core agent loop — runs until completion, approval needed, or step limit."""
    client = _get_client()

    while step_count < MAX_AGENT_STEPS:
        step_count += 1
        logger.info(f"[{run_id}] Step {step_count}/{MAX_AGENT_STEPS}")

        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "system", "content": _add_date_to_system()}] + messages,
                tools=ALL_TOOL_DEFS,
                tool_choice="auto",
                max_tokens=4096,
            )
        except APIConnectionError as e:
            return AgentRunResult(
                run_id=run_id,
                error=f"Connection error: {e}",
                step_count=step_count,
                tools_called=tool_calls_log,
            )
        except AuthenticationError:
            return AgentRunResult(
                run_id=run_id,
                error="Invalid API key. Check your GOOGLE_API_KEY in .env",
                step_count=step_count,
                tools_called=tool_calls_log,
            )
        except Exception as e:
            return AgentRunResult(
                run_id=run_id,
                error=f"LLM error: {e}",
                step_count=step_count,
                tools_called=tool_calls_log,
            )

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        # ── Final text response ─────────────────────────────────────────────────
        if finish_reason == "stop":
            text = choice.message.content or "Done."
            return AgentRunResult(
                run_id=run_id,
                response_text=text,
                step_count=step_count,
                tools_called=tool_calls_log,
            )

        # ── Tool use ────────────────────────────────────────────────────────────
        if finish_reason == "tool_calls":
            tool_calls = choice.message.tool_calls or []

            # Add assistant message with tool calls
            messages = messages + [
                {
                    "role": "assistant",
                    "content": choice.message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            ]

            tool_result_messages = []

            for tc in tool_calls:
                tool_name = tc.function.name
                tool_id = tc.id
                try:
                    tool_input = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_input = {}

                record = ToolCallRecord(
                    step=step_count,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    tool_input=tool_input,
                )

                # ── Approval required? ──────────────────────────────────────────
                if tool_name in APPROVAL_REQUIRED_TOOLS:
                    record.approved = None
                    tool_calls_log.append(record)
                    return AgentRunResult(
                        run_id=run_id,
                        pending_approval=PendingApproval(
                            run_id=run_id,
                            log_id=log_id,
                            tool_use_id=tool_id,
                            tool_name=tool_name,
                            tool_input=tool_input,
                            messages=messages,
                            step_count=step_count,
                            tool_calls_log=tool_calls_log,
                            human_description=_human_description(tool_name, tool_input),
                        ),
                        step_count=step_count,
                        tools_called=tool_calls_log,
                    )

                # ── Execute immediately (read tool) ─────────────────────────────
                retry_key = f"{tool_name}_{step_count}"
                try:
                    result = execute_tool(tool_name, tool_input)
                    record.tool_result = result
                    record.approved = True
                    tool_result_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": json.dumps(result),
                    })
                    logger.info(f"[{run_id}] Tool {tool_name} → success={result.get('success')}")
                except Exception as e:
                    tool_retries[retry_key] = tool_retries.get(retry_key, 0) + 1
                    record.error = str(e)
                    err_result = {"success": False, "error": str(e)}
                    record.tool_result = err_result
                    tool_result_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": json.dumps(err_result),
                    })
                    if tool_retries[retry_key] >= MAX_TOOL_RETRIES:
                        logger.warning(f"[{run_id}] Tool {tool_name} failed {MAX_TOOL_RETRIES} times")

                tool_calls_log.append(record)

            messages = messages + tool_result_messages
            continue

        # Unexpected finish reason
        return AgentRunResult(
            run_id=run_id,
            error=f"Unexpected finish reason: {finish_reason}",
            step_count=step_count,
            tools_called=tool_calls_log,
        )

    return AgentRunResult(
        run_id=run_id,
        error=f"Agent reached the maximum step limit ({MAX_AGENT_STEPS}). Request may be too complex.",
        step_count=step_count,
        tools_called=tool_calls_log,
    )


def run_agent(
    user_message: str,
    conversation_history: List[dict],
) -> AgentRunResult:
    """Start a new agent run with a user message."""
    if not user_message.strip():
        return AgentRunResult(run_id=new_run_id(), error="Empty message.")

    run_id = new_run_id()
    log_id = repo.create_log(run_id, user_message, LLM_MODEL)

    messages = conversation_history + [{"role": "user", "content": user_message}]
    start_ms = int(time.time() * 1000)

    result = _run_loop(
        messages=messages,
        run_id=run_id,
        log_id=log_id,
        step_count=0,
        tool_calls_log=[],
        tool_retries={},
    )

    _finalize_log(log_id, result, start_ms)
    return result


def resume_after_approval(
    pending: PendingApproval,
    approved: bool,
) -> AgentRunResult:
    """Resume an agent run after human approval decision."""
    start_ms = int(time.time() * 1000)

    if approved:
        try:
            tool_result = execute_tool(pending.tool_name, pending.tool_input)
            for r in pending.tool_calls_log:
                if r.tool_id == pending.tool_use_id:
                    r.tool_result = tool_result
                    r.approved = True
        except Exception as e:
            tool_result = {"success": False, "error": str(e)}
    else:
        tool_result = {
            "success": False,
            "status": "rejected",
            "message": "Action was rejected by the user.",
        }
        for r in pending.tool_calls_log:
            if r.tool_id == pending.tool_use_id:
                r.approved = False

    messages = pending.messages + [
        {
            "role": "tool",
            "tool_call_id": pending.tool_use_id,
            "content": json.dumps(tool_result),
        }
    ]

    result = _run_loop(
        messages=messages,
        run_id=pending.run_id,
        log_id=pending.log_id,
        step_count=pending.step_count,
        tool_calls_log=pending.tool_calls_log,
        tool_retries={},
    )

    _finalize_log(pending.log_id, result, start_ms)
    return result


def _finalize_log(log_id: int, result: AgentRunResult, start_ms: int):
    end_ms = int(time.time() * 1000)
    status = "awaiting_approval" if result.needs_approval else ("error" if result.error else "completed")
    repo.update_log(
        log_id,
        tools_called=[
            {
                "step": r.step,
                "name": r.tool_name,
                "approved": r.approved,
                "success": r.tool_result.get("success") if r.tool_result else None,
                "error": r.error,
            }
            for r in result.tools_called
        ],
        step_count=result.step_count,
        errors=[r.error for r in result.tools_called if r.error],
        status=status,
        final_outcome=result.response_text or result.error,
        end_time=datetime.utcnow(),
        duration_ms=end_ms - start_ms,
    )
