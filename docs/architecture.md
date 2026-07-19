# Architecture — Productivity Agent

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Browser)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │  HTTPS / Streamlit WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                     STREAMLIT FRONTEND                          │
│  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │  Chat Window  │  │  Approval Card  │  │  Task/Note/Log   │  │
│  │  + st.status  │  │  (approve/deny) │  │  Panels          │  │
│  └───────┬───────┘  └────────┬────────┘  └──────────────────┘  │
└──────────│──────────────────│────────────────────────────────────┘
           │                  │
┌──────────▼──────────────────▼────────────────────────────────────┐
│                        AGENT CONTROLLER                          │
│  app/agent/agent.py                                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  run_agent(user_msg, history, status_fn) → AgentRunResult  │  │
│  │  resume_after_approval(pending, approved, status_fn)        │  │
│  └──────────────┬───────────────────────────────────────────┘   │
│                 │                                                │
│  ┌──────────────▼──────────────────────────────────────────┐    │
│  │                    AGENT LOOP                           │    │
│  │  seen_calls = set()    # duplicate detection            │    │
│  │  while step < MAX_STEPS (8):                            │    │
│  │    1. status_fn("🧠 Step N: thinking...")               │    │
│  │    2. Call LLM API (Groq / llama-3.3-70b-versatile)    │    │
│  │    3. Parse response (text / tool_calls)                │    │
│  │    4. For each tool call:                               │    │
│  │       a. status_fn("🔧 Selected tool: `name`")         │    │
│  │       b. Check duplicate — block if seen before         │    │
│  │       c. Check if approval required                     │    │
│  │          YES → return PendingApproval                   │    │
│  │          NO  → status_fn("⚙️ Executing: `name`...")    │    │
│  │              → execute with 30s timeout                 │    │
│  │              → status_fn("✅ `name` completed")         │    │
│  │    5. Add tool results to messages                      │    │
│  │    6. Repeat                                            │    │
│  │  status_fn("✍️ Producing final response...")            │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────┬─────────────────────────┬───────────────────────────┘
             │                         │
┌────────────▼──────────┐  ┌───────────▼──────────────────────────┐
│     LLM API           │  │           TOOL REGISTRY              │
│  Groq (OpenAI-compat) │  │  app/tools/                          │
│  llama-3.3-70b        │  │  ┌─────────────────────────────────┐ │
│                       │  │  │  task_tools.py (5 tools)        │ │
│  Tool definitions     │  │  │  - create_task  [WRITE]         │ │
│  sent as JSON schema  │  │  │  - list_tasks   [READ]          │ │
│  (OpenAI format)      │  │  │  - update_task  [WRITE]         │ │
│                       │  │  │  - complete_task [WRITE]        │ │
│  Model returns:       │  │  │  - delete_task  [WRITE]         │ │
│  - text response, OR  │  │  ├─────────────────────────────────┤ │
│  - tool_calls array   │  │  │  note_tools.py (2 tools)        │ │
└───────────────────────┘  │  │  - save_note   [WRITE]          │ │
                           │  │  - search_notes [READ]          │ │
                           │  │    + date range filter          │ │
                           │  ├─────────────────────────────────┤ │
                           │  │  planning_tools.py (3 tools)    │ │
                           │  │  - extract_meeting_actions [READ]│ │
                           │  │  - generate_work_plan [READ]    │ │
                           │  │  - generate_weekly_report [READ]│ │
                           │  ├─────────────────────────────────┤ │
                           │  │  __init__.py (router)           │ │
                           │  │  - 30s timeout per tool         │ │
                           │  │  - ThreadPoolExecutor           │ │
                           │  └─────────────────────────────────┘ │
                           └──────────────┬───────────────────────┘
                                          │
                           ┌──────────────▼───────────────────────┐
                           │          DATABASE LAYER               │
                           │  app/database/                        │
                           │  ┌─────────────────────────────────┐ │
                           │  │  models.py (SQLAlchemy 2.0)     │ │
                           │  │  - TaskModel (11 fields)        │ │
                           │  │  - NoteModel (7 fields)         │ │
                           │  │  - ExecutionLogModel            │ │
                           │  ├─────────────────────────────────┤ │
                           │  │  repository.py (CRUD layer)     │ │
                           │  └────────────────┬────────────────┘ │
                           └───────────────────│──────────────────┘
                                               │
                           ┌───────────────────▼──────────────────┐
                           │         SQLite Database               │
                           │  data/productivity.db                 │
                           │  - tasks table                        │
                           │  - notes table                        │
                           │  - execution_logs table               │
                           └──────────────────────────────────────┘
```

---

## Human Approval Flow

```
Agent selects a write tool (create_task / update_task / complete_task /
delete_task / save_note)
         │
         ▼
  Tool in APPROVAL_REQUIRED_TOOLS?
         │
    YES  │  NO
         │    └──► execute_tool() with 30s timeout → continue loop
         ▼
  Return AgentRunResult(pending_approval=PendingApproval(...))
         │
         ▼
  Streamlit renders Approval Card:
  ┌─────────────────────────────────────────────┐
  │  ⚠️  Approval Required                      │
  │  Tool:    create_task                        │
  │  Action:  Create task: "Review API docs"     │
  │  ▶ View full parameters (JSON)               │
  │  [✅ Approve]  [❌ Reject]                   │
  └─────────────────────────────────────────────┘
         │
  User clicks Approve / Reject
         │
         ▼
  resume_after_approval(pending, approved, status_fn)
         │
    APPROVED: execute_tool() → add result to messages → continue loop
    REJECTED: inject rejection message → LLM acknowledges → stop
         │
         ▼
  Agent generates final response
```

---

## Session Memory

The agent maintains conversational context through:

1. **`st.session_state.conversation`** — display-layer messages shown in chat
2. **`api_messages`** — raw message history reconstructed from conversation and passed to the LLM on every turn
3. **`pending_approval`** — serialised mid-run state (full message history, step count, tool log) stored in session state while the user reviews an approval

When a multi-step workflow is paused for approval, the entire LLM message history is preserved in `PendingApproval.messages`, allowing the loop to resume exactly where it left off with full context.

---

## Agent Execution Limits

| Limit | Value | Why |
|-------|-------|-----|
| `MAX_AGENT_STEPS` | 8 | Sufficient for complex multi-step workflows (meeting → 5 tasks + summary = 7 steps). Prevents runaway loops. |
| `MAX_TOOL_RETRIES` | 2 | One automatic retry for transient errors, then surface to user. More retries waste tokens and time. |
| `TOOL_TIMEOUT_SECONDS` | 30 | LLM-powered sub-calls (`extract_meeting_actions`) can take 10–15 s. 30 s is safe without feeling frozen. |
| Duplicate call block | — | Identical (tool_name + args) calls within one agent turn are blocked. Prevents the model from looping on the same operation. |

---

## Error Handling

| Error Type | Where Caught | User-Facing Message |
|---|---|---|
| Missing API key | `main.py` sidebar | "❌ No API Key — add GROQ_API_KEY to .env" |
| LLM connection error | `agent.py` try/except | "Connection error: …" |
| LLM auth error | `agent.py` try/except | "Invalid API key. Check your GROQ_API_KEY" |
| Invalid tool arguments | `task_tools.py` Pydantic | "priority must be one of {…}" |
| Unknown task ID | `repository.py` | "Task #N not found" |
| Tool timeout | `tools/__init__.py` ThreadPool | "Tool 'name' timed out after 30s" |
| Tool execution error | `tools/__init__.py` | Structured error passed to LLM |
| Max steps exceeded | `agent.py` loop exit | "Agent reached the maximum step limit (8)" |
| Empty user input | `agent.py` pre-check | "Empty message." |
| Duplicate tool call | `agent.py` seen_calls | "Duplicate call: already called with identical arguments" |

Stack traces and API keys are never shown in the UI.

---

## Execution Log Schema

Every agent run writes to `execution_logs` with:

```json
{
  "run_id": "run_a1b2c3d4",
  "user_request": "Create a task to review the docs",
  "model": "llama-3.3-70b-versatile",
  "tools_called": [
    {
      "step": 1,
      "name": "create_task",
      "input": {"title": "Review the docs", "priority": "high"},
      "result": {"success": true, "task": {"id": 7, "title": "Review the docs"}},
      "approved": true,
      "success": true,
      "error": null
    }
  ],
  "step_count": 1,
  "errors": [],
  "status": "completed",
  "start_time": "2026-07-20 10:00:00",
  "end_time": "2026-07-20 10:00:05",
  "duration_ms": 5210,
  "final_outcome": "Task #7 created: Review the docs"
}
```

---

## Data Flow — Meeting Notes to Tasks (Workflow A)

```
User: "Here are my meeting notes, create tasks from them"
         │
         ▼
1. Agent calls extract_meeting_actions(meeting_notes)
   → Groq LLM extracts decisions, action items, owners, deadlines (JSON)
         │
         ▼
2. Agent presents extracted action items to user
   → Shows proposed task titles, priorities, and deadlines
         │
         ▼
3. Agent calls create_task() for each action item
   → System pauses for approval (one per task)
         │
         ▼
4. User approves each task
   → Agent creates the task, continues to the next
         │
         ▼
5. Agent reports all created task IDs in a summary
```

---

## Data Flow — Daily Planning (Workflow B)

```
User: "Make me a work plan for today with 6 hours"
         │
         ▼
1. generate_work_plan(available_hours=6, date="2026-07-20")
   → list_tasks(status="pending") + in_progress + blocked
   → Score each task: priority (4/3/2/1) + overdue bonus + tag match
   → Sort by score, fill schedule until hours exhausted
   → Flag blocked tasks and overdue items as risk warnings
         │
         ▼
2. Agent formats and presents the ordered schedule
   → Scheduled tasks with estimated hours
   → Deferred tasks
   → Risk warnings
   → Recommended focus areas (top 3)
```

---

## Data Flow — Weekly Review (Workflow C)

```
User: "Show me my weekly report"
         │
         ▼
1. generate_weekly_report()
   → list_tasks(limit=200) → split into buckets:
     completed / overdue / blocked / pending / in_progress
   → next_week_priorities = top 5 high/critical pending tasks
         │
         ▼
2. Agent presents the report:
   → Statistics (counts per status)
   → Completed tasks this week
   → Overdue and blocked items
   → Recommended priorities for next week
```
