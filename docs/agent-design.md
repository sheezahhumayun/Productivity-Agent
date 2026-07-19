# Agent Design Document — Productivity Agent

> Assignment 2 | AI Summer Fellowship 2026 | Week 3
> Track 2: NLP & AI Agents

---

## 1. Problem Statement

Knowledge workers spend a significant portion of their working day managing tasks
and notes across disconnected tools — sticky notes, spreadsheets, email, and chat.
Switching contexts to record action items, search past notes, or plan the day
introduces friction that causes work to slip through the cracks.

The Productivity Agent solves this by providing a single conversational interface
that can create and manage tasks, store and retrieve notes, extract structured
action items from unstructured meeting notes, and produce prioritised daily work
plans — all while requiring explicit human approval before any data is changed.

The core insight is that AI should reduce friction, not replace judgment. Write
operations are guarded by an approval step so the user remains in control at all
times.

---

## 2. Users

**Primary user:** An individual knowledge worker (developer, analyst, project
manager) who:
- Manages 10–50 concurrent tasks
- Takes meeting notes that produce follow-up action items
- Needs a quick way to plan and prioritise a working day
- Works on a single device (no multi-user or team collaboration required)
- Has a Groq API key and basic comfort with web interfaces

**Secondary user:** A technical evaluator (fellowship instructor, peer reviewer)
assessing the agent's correctness, safety, and design quality.

The system is not designed for:
- Teams sharing a workspace
- Mobile or offline use
- Mission-critical task management (no SLA guarantees)

---

## 3. Use Cases

### UC-01 — Create a task from natural language
User describes a task in conversation. Agent extracts title, priority, due date,
and tags, proposes the task, and asks for approval before writing to the database.

### UC-02 — List and filter tasks
User asks to see tasks by status, priority, due date, or tag. Agent calls
`list_tasks` and presents results.

### UC-03 — Update a task
User asks to change a task's priority, status, due date, or title. Agent shows
the proposed change and asks for approval.

### UC-04 — Complete or delete a task
User marks a task done or asks to remove it. Agent shows confirmation details
and asks for approval, noting that deletion is irreversible.

### UC-05 — Save a note
User dictates or pastes text to be saved as a note with a category and tags.
Agent proposes the note and asks for approval.

### UC-06 — Search notes
User asks for notes about a topic, category, or date range. Agent searches
by keyword and returns ranked results.

### UC-07 — Extract meeting actions
User pastes meeting notes or a transcript. Agent calls `extract_meeting_actions`
to produce a structured summary with decisions, action items (owner, deadline,
priority), and unresolved questions. Agent then proposes creating tasks for each
action item.

### UC-08 — Generate a daily work plan
User asks for today's plan with a stated number of available hours. Agent
retrieves all open tasks, scores them by priority and due date, schedules them
within the hour budget, and flags overdue and blocked items.

### UC-09 — Generate a weekly report
User asks for a productivity summary. Agent retrieves all tasks, computes
statistics (completed, overdue, blocked, pending), and recommends next-week
priorities.

### UC-10 — Session references
User refers to a previously listed item ("mark the second one complete"). Agent
resolves the reference from conversation history and proceeds with the approval
flow.

---

## 4. Agent Responsibilities

The agent is authorised to:

| Responsibility | Detail |
|---|---|
| Read tasks | List and filter from the database at any time |
| Read notes | Search notes at any time |
| Propose write operations | Create tasks, create notes, update tasks, complete tasks, delete tasks — but only after showing the user a full description and receiving approval |
| Call planning tools | Run `generate_work_plan` and `generate_weekly_report` without approval |
| Call `extract_meeting_actions` | Parse meeting notes using the LLM without approval (read-only, no writes) |
| Chain tools | Call multiple tools in sequence within a single agent turn (up to 8 steps) |
| Manage session context | Maintain conversation history so the user can make references to prior turns |
| Report errors | Explain failed tool calls clearly without exposing stack traces or secrets |

---

## 5. Agent Boundaries

The agent is NOT allowed to:

| Boundary | Reason |
|---|---|
| Execute any write tool without explicit approval | Prevents accidental data modification |
| Send emails or external messages | No email tool implemented; scope is local productivity only |
| Access the filesystem, internet, or external services | No such tools registered |
| Bypass the step limit (8) | Prevents runaway loops and excessive API costs |
| Retry a tool more than twice | Repeated failures indicate a real error; surfacing it is safer than looping |
| Execute duplicate tool calls | Identical (name + args) calls in the same turn are blocked to prevent loops |
| Expose API keys, database paths, or system internals | Safety rule in system prompt; never included in responses or logs |
| Make decisions on behalf of the user for irreversible actions | Human approval is mandatory |
| Invent task IDs, counts, or results | Must always use live tool output |

---

## 6. Tool Catalogue

### Read Tools (no approval)

| Tool | Input | Output | Purpose |
|---|---|---|---|
| `list_tasks` | status, priority, due_before, tag (all optional) | tasks[], count | Retrieve tasks with filters |
| `search_notes` | query, category, date_from, date_to (optional) | notes[], count | Keyword search notes |
| `extract_meeting_actions` | meeting_notes, meeting_title (optional) | summary, decisions, action_items[], unresolved_questions[] | LLM-powered meeting analysis |
| `generate_work_plan` | available_hours, date, priorities (optional) | scheduled_tasks, deferred_tasks, risk_warnings, recommended_focus | Day plan from pending tasks |
| `generate_weekly_report` | (none) | statistics, completed_tasks, overdue_tasks, blocked_tasks, next_week_priorities | Weekly productivity summary |

### Write Tools (approval required)

| Tool | Input | Output | Approval trigger |
|---|---|---|---|
| `create_task` | title, description, priority, due_date, tags | task, task_id | Before any task creation |
| `update_task` | task_id + any fields | updated_task | Before any task modification |
| `complete_task` | task_id | updated_task with status=completed | Before marking complete |
| `delete_task` | task_id | success confirmation | Before permanent deletion |
| `save_note` | title, content, category, tags | note, note_id | Before any note creation |

Full input/output schemas are in [`docs/tool-specifications.md`](tool-specifications.md).

---

## 7. State Model

The agent uses three layers of state during execution.

### 7.1 Conversational State (`st.session_state`)

Maintained by the Streamlit UI across page interactions within a session:

| Key | Type | Purpose |
|---|---|---|
| `conversation` | list[dict] | Display-layer messages: {role, content, timestamp, tools_called} |
| `api_messages` | list[dict] | Raw LLM message history (user + assistant only) |
| `pending_approval` | PendingApproval or None | Mid-run state when a write tool is waiting for approval |
| `agent_status` | str | One of: idle / thinking / awaiting_approval |

### 7.2 Mid-Run State (`PendingApproval` dataclass)

Serialised when the loop pauses for approval. Stored in session state until the
user responds.

```python
@dataclass
class PendingApproval:
    run_id: str           # unique run identifier
    log_id: int           # DB log row ID
    tool_use_id: str      # LLM-assigned tool call ID
    tool_name: str        # name of the tool awaiting approval
    tool_input: dict      # full arguments as parsed from the LLM
    messages: list[dict]  # complete message history at pause point
    step_count: int       # how many steps have already run
    tool_calls_log: list  # all ToolCallRecords for this run so far
    human_description: str # plain-English description of the action
```

When the user approves or rejects, `resume_after_approval()` uses this state to
continue the loop from exactly where it paused, with the full message context
preserved.

### 7.3 Persistent State (SQLite)

Three tables persist data across sessions:

| Table | Key fields | Purpose |
|---|---|---|
| `tasks` | id, title, description, priority, status, due_date, tags, source, notes, created_at, updated_at | Task storage |
| `notes` | id, title, content, category, tags, created_at, updated_at | Note storage |
| `execution_logs` | run_id, user_request, model, tools_called (JSON), step_count, errors, status, start_time, end_time, duration_ms, final_outcome | Full audit trail per agent run |

---

## 8. Approval Model

The approval system is enforced at the infrastructure level, not only in the system
prompt. When the agent loop encounters a tool in `APPROVAL_REQUIRED_TOOLS`, it
immediately returns a `PendingApproval` result to the UI regardless of what the
LLM requested.

### Approval trigger set

```python
APPROVAL_REQUIRED_TOOLS = {
    "create_task",    # persistent write
    "update_task",    # modifies existing data
    "complete_task",  # status change (often treated as irreversible)
    "delete_task",    # permanent, irreversible deletion
    "save_note",      # persistent write
}
```

### Approval UI

The approval card shows:
1. **Tool name** in monospace
2. **Human-readable action** — e.g., "Create task: 'Review API docs' (priority: high, due: 2026-08-01)"
3. **Full JSON parameters** in an expandable section
4. **[✅ Approve]** button — executes the tool and continues the agent loop
5. **[❌ Reject]** button — sends a rejection message to the LLM, which acknowledges and stops

### Rejection handling

When the user rejects, the tool result sent back to the LLM is:
```json
{"success": false, "status": "rejected", "message": "Action was rejected by the user."}
```

The LLM then responds naturally ("Understood, I won't create that task.") and the
turn ends without executing any further write operations.

### Approval bypass prevention

The system prompt states: "Never attempt to bypass the approval system." The
approval check is also enforced in code (`if tool_name in APPROVAL_REQUIRED_TOOLS:
return PendingApproval(...)`) before any tool execution, so even if the LLM ignores
the prompt, the code still enforces the gate.

---

## 9. Error Strategy

### Error taxonomy

| Error class | Examples | Handling |
|---|---|---|
| Input validation | Invalid priority, missing title | Pydantic raises before execution; LLM reports to user |
| Not found | Task #99999 does not exist | Tool returns `{"success": false, "error": "Task #99999 not found"}` |
| Tool timeout | Slow LLM sub-call in `extract_meeting_actions` | `ThreadPoolExecutor.result(timeout=30)` raises; error returned to LLM |
| Duplicate tool call | LLM tries the same (name+args) twice | Blocked with error result; LLM is instructed to try a different approach |
| Max retries exceeded | Same tool fails twice | After second failure the LLM is advised to stop retrying |
| Max steps exceeded | 8-step limit hit | Loop exits; agent reports what was completed and stops |
| LLM API errors | Connection error, auth failure | Caught in try/except; user-friendly message shown in chat |
| Empty input | User submits blank message | Rejected before LLM call: "Empty message." |

### Principles

1. **Never expose internals** — stack traces, API keys, and database paths never
   appear in UI messages.
2. **Always surface errors** — tool failures are included in the message history so
   the LLM can explain them naturally.
3. **Degrade gracefully** — partial results from multi-step workflows are reported;
   the run does not silently abandon completed steps.
4. **Log everything** — every error is recorded in the execution log with its run
   ID for post-hoc review.

---

## 10. Security Considerations

### Secrets management

- API keys are read from environment variables or `st.secrets` (Streamlit Cloud).
- Keys are never hard-coded, logged, or shown in the UI.
- The `.gitignore` excludes `.env` files.

### Prompt injection

- User input is passed as a `role: user` message, not string-interpolated into
  the system prompt.
- The system prompt explicitly forbids the agent from exposing internals.
- Tool outputs are passed as structured `role: tool` messages, not interpolated
  into prompts.

### Tool permission model

- The tool router only dispatches to explicitly registered functions.
- Unknown tool names return `{"success": false, "error": "Unknown tool: name"}`.
- No tool has filesystem, network, or shell access.

### Data privacy

- Only task and note content that the user explicitly provides is stored.
- Execution logs store the user request and tool results; they do not store the
  LLM's chain-of-thought or intermediate reasoning.
- No analytics, telemetry, or external data sharing.

### Destructive actions

- `delete_task` requires approval and the approval card explicitly states
  "(irreversible)" in the human description.
- There is no bulk-delete operation.

See [`docs/security-review.md`](security-review.md) for the full risk assessment.
