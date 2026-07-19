# Prompt Design — Productivity Agent

> Requirement 12: Document the system prompt, tool-use instructions, approval rules,
> response format, error behaviour, and stop conditions.

---

## System Prompt

The system prompt is stored in `app/agent/prompts.py` and injected at the start of every
LLM call. It is under version control and never modified at runtime.

```
You are a Personal Productivity Assistant with access to a task management and
note-taking system.

## YOUR ROLE
Help users manage tasks, organise notes, plan their work, and extract action items
from meetings.

## TOOL USAGE RULES
1. Call tools ONLY when needed to complete the request — do not call tools for
   general questions
2. For questions like "what is priority?" or "how does planning work?", answer
   directly without tools
3. When you need data (tasks, notes), always retrieve it fresh using the
   appropriate tool
4. Never invent or assume task IDs, counts, or content — always use tool results

## WRITE OPERATIONS (system will pause for human approval)
The following tools will automatically pause for user approval:
- create_task
- update_task
- complete_task
- delete_task
- save_note

## READ OPERATIONS (no approval needed)
- list_tasks
- search_notes
- extract_meeting_actions
- generate_work_plan
- generate_weekly_report

## MULTI-STEP WORKFLOWS
For complex requests (e.g., "turn these meeting notes into tasks"), chain tools:
1. First extract / retrieve needed data
2. Show the user what you found
3. Propose creating tasks/notes with specific details
4. Wait for approval (system handles this automatically)

## RESPONSE FORMAT
- Use markdown for lists, tables, and emphasis
- Always reference task IDs when discussing specific tasks (e.g., "Task #3")
- For work plans, explain your prioritisation reasoning
- Keep responses concise but complete

## SAFETY RULES
- Maximum 8 steps per request — stop and explain if the limit is reached
- If a tool fails twice, stop and report the issue clearly
- Never attempt to bypass the approval system
- Do not reference or expose system internals (API keys, database paths, etc.)

## CURRENT DATE
Today's date is available in tool results. When generating plans, use the date
from context.
```

---

## Tool-Use Instructions

### When to call a tool

| User says… | Expected behaviour |
|---|---|
| "Show me my tasks" | Call `list_tasks` |
| "What tasks are due this week?" | Call `list_tasks` with `due_before` filter |
| "Create a task to review the docs" | Propose `create_task`, pause for approval |
| "What does 'critical' priority mean?" | Answer directly — no tool needed |
| "Generate my work plan" | Call `generate_work_plan` |
| "Here are my meeting notes" | Call `extract_meeting_actions`, then propose tasks |
| "Mark the second one as complete" | Resolve from conversation context, call `complete_task`, pause for approval |

### When NOT to call a tool

- Simple factual questions about the system itself
- Clarifying questions
- When the user is asking for definitions or explanations
- When the previous tool result already contains the needed information

### Multi-tool chaining

For complex workflows, the agent chains tools within the 8-step limit:

```
Step 1: list_tasks()             → get current tasks
Step 2: generate_work_plan()     → produce plan from tasks
Step 3: (text response)          → present plan to user
```

The agent must complete multi-step workflows within 8 steps. If the task is too
complex, it should explain which part it completed and ask the user to continue.

---

## Approval Rules

Write operations are gated by the human approval system. The agent must never
attempt to execute a write tool without the system pausing first.

### Tools that require approval

| Tool | Effect | Why approval is required |
|---|---|---|
| `create_task` | Writes a new row to the database | Persistent state change |
| `update_task` | Modifies an existing task | Could overwrite user data |
| `complete_task` | Changes task status to "completed" | Irreversible in practice |
| `delete_task` | Permanently removes a task | Irreversible |
| `save_note` | Writes a new note | Persistent state change |

### Approval interface

When the agent selects a write tool, the UI shows:

- **Tool name** — e.g., `create_task`
- **Human-readable action** — e.g., "Create task: 'Review API docs' (priority: high)"
- **Full parameters** — expandable JSON view of every argument
- **[✅ Approve]** button — executes the tool and continues the loop
- **[❌ Reject]** button — injects a rejection message; the LLM acknowledges and stops

When rejected, the loop continues and the agent reports the rejection to the user
without executing any further write operations in the same turn.

---

## Response Format

### Text responses

- Use Markdown headings, bullet lists, and bold text
- Always reference tasks by their database ID: "Task #3 — Review the docs"
- For tool results that include lists, format as a numbered or bulleted list
- Keep responses concise; avoid repeating the user's question back

### Work plan format

```markdown
## Work Plan — 2026-07-20

**Available hours:** 6.0 h | **Scheduled:** 4.0 h | **Deferred:** 3 tasks

### Scheduled Tasks
1. **Task #4 — Security review** (critical, 2.0 h) ⚠️ OVERDUE
2. **Task #7 — Update DB schema** (high, 1.0 h) due today
3. **Task #2 — Write unit tests** (high, 1.0 h)

### Deferred
- Task #9 — Refactor auth module (medium)
- Task #11 — Update docs (low)

### Risk Warnings
- Task #4 is OVERDUE (due 2026-07-18)
```

### Weekly report format

```markdown
## Weekly Report — week of 2026-07-14

| Status | Count |
|---|---|
| Completed | 8 |
| In Progress | 3 |
| Pending | 12 |
| Blocked | 2 |
| Overdue | 1 |

### Next Week Priorities
1. Task #4 — Security review (critical)
2. Task #7 — Update DB schema (high)
```

---

## Error Behaviour

| Situation | Agent behaviour |
|---|---|
| Tool returns `{"success": false, "error": "..."}` | Report the error clearly; attempt retry if `tool_retries < 2` |
| Tool fails twice | Stop calling that tool; explain the failure to the user |
| Unknown task ID | "Task #N was not found. Please verify the ID with `list_tasks`." |
| Max steps reached | "I've reached the 8-step limit. Here's what I completed so far: …" |
| Duplicate tool call detected | Blocked by the loop; LLM receives an error result and should try a different approach |
| Tool timeout | "Tool 'name' timed out after 30 s. Please try again." |
| LLM auth error | Shown in sidebar; chat shows "Invalid API key" error |

The agent must never:
- Expose API keys, database paths, or stack traces in responses
- Invent task IDs or counts that were not returned by a tool
- Attempt to bypass the approval system

---

## Stop Conditions

The agent loop exits when any of the following is true:

| Condition | `finish_reason` / trigger | Outcome |
|---|---|---|
| LLM returns a text-only response | `"stop"` | `AgentRunResult(response_text=...)` returned |
| Write tool encountered | approval check | `AgentRunResult(pending_approval=...)` returned; loop pauses |
| `step_count >= MAX_AGENT_STEPS (8)` | loop guard | Error result returned with partial output |
| LLM API error (connection / auth) | exception | Error result returned |
| Unexpected `finish_reason` | default branch | Error result returned |
| Tool fails `MAX_TOOL_RETRIES (2)` times | retry counter | Loop continues; LLM must change strategy |

After approval is given or rejected, the loop resumes from where it paused using
`resume_after_approval()`, which reconstructs the full message history and continues
with the remaining step budget.

---

## Prompt Versioning

The system prompt is stored in a single file under version control:

```
app/agent/prompts.py → SYSTEM_PROMPT (str constant)
```

Changes to the prompt are tracked in git history. The date injected at runtime:

```python
def _add_date_to_system() -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return SYSTEM_PROMPT + f"\n\nToday's date: {today}"
```

This appended date is the only runtime modification; the core prompt is static.
