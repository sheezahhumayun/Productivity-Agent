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
│  │  (messages)   │  │  (approve/deny) │  │  Panels          │  │
│  └───────┬───────┘  └────────┬────────┘  └──────────────────┘  │
└──────────│──────────────────│────────────────────────────────────┘
           │                  │
┌──────────▼──────────────────▼────────────────────────────────────┐
│                        AGENT CONTROLLER                          │
│  app/agent/agent.py                                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  run_agent(user_message, history) → AgentRunResult         │  │
│  │  resume_after_approval(pending, approved) → AgentRunResult  │  │
│  └──────────────┬───────────────────────────────────────────┘   │
│                 │                                                │
│  ┌──────────────▼──────────────────────────────────────────┐    │
│  │                    AGENT LOOP                           │    │
│  │  while step < MAX_STEPS:                                │    │
│  │    1. Call LLM API                                      │    │
│  │    2. Parse response (text / tool_use)                  │    │
│  │    3. If tool_use:                                      │    │
│  │       a. Check if approval required                     │    │
│  │       b. If yes → return PendingApproval               │    │
│  │       c. If no  → execute immediately                   │    │
│  │    4. Add tool result to messages                       │    │
│  │    5. Repeat                                            │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────┬─────────────────────────┬───────────────────────────┘
             │                         │
┌────────────▼──────────┐  ┌───────────▼──────────────────────────┐
│     LLM API           │  │           TOOL REGISTRY              │
│  (Anthropic Claude)   │  │  app/tools/                          │
│                       │  │  ┌─────────────────────────────────┐ │
│  Tool definitions     │  │  │  task_tools.py                  │ │
│  sent as JSON schema  │  │  │  - create_task  [WRITE]         │ │
│                       │  │  │  - list_tasks   [READ]          │ │
│  Model returns:       │  │  │  - update_task  [WRITE]         │ │
│  - text response, OR  │  │  │  - complete_task [WRITE]        │ │
│  - tool_use blocks    │  │  │  - delete_task  [WRITE]         │ │
└───────────────────────┘  │  ├─────────────────────────────────┤ │
                           │  │  note_tools.py                  │ │
                           │  │  - save_note   [WRITE]          │ │
                           │  │  - search_notes [READ]          │ │
                           │  ├─────────────────────────────────┤ │
                           │  │  planning_tools.py              │ │
                           │  │  - extract_meeting_actions [READ]│ │
                           │  │  - generate_work_plan [READ]    │ │
                           │  │  - generate_weekly_report [READ]│ │
                           │  └─────────────────────────────────┘ │
                           └──────────────┬───────────────────────┘
                                          │
                           ┌──────────────▼───────────────────────┐
                           │          DATABASE LAYER               │
                           │  app/database/                        │
                           │  ┌─────────────────────────────────┐ │
                           │  │  models.py (SQLAlchemy)         │ │
                           │  │  - TaskModel                    │ │
                           │  │  - NoteModel                    │ │
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

## Human Approval Flow

```
Agent calls write tool
         │
         ▼
  Tool in APPROVAL_REQUIRED_TOOLS?
         │
    YES  │  NO
         │    └──► Execute immediately → continue loop
         ▼
  Return AgentRunResult(pending_approval=...)
         │
         ▼
  Streamlit shows Approval Card
  - Tool name
  - Human-readable description
  - Full parameters (expandable)
  - [Approve] / [Reject] buttons
         │
  User clicks Approve / Reject
         │
         ▼
  resume_after_approval(pending, approved)
         │
    APPROVED: execute_tool() → continue loop
    REJECTED: inject rejection message → continue loop
         │
         ▼
  Agent generates final response
```

## Session Memory

The agent maintains conversational context through:
1. **`st.session_state.conversation`** — display-layer messages (user/assistant/system)
2. **`api_messages`** — raw API message history passed to the LLM on each turn
3. **`pending_approval`** — serialized mid-run state (messages, step count, tool log)

When a multi-step workflow is paused for approval, the entire LLM message history is preserved in `PendingApproval.messages`, allowing the loop to resume exactly where it left off.

## Error Handling

| Error Type | Handling |
|---|---|
| Missing API key | Shown in sidebar; chat input disabled |
| LLM connection error | User-friendly error in chat |
| Invalid tool arguments | Pydantic validation raises before execution |
| Tool execution failure | Error result returned to LLM; LLM reports to user |
| Max steps exceeded | Clear error message; partial results shown |
| Unknown task ID | Graceful "not found" message |
| Empty user input | Rejected before LLM call |

## Data Flow — Meeting Notes to Tasks (Multi-Step Workflow)

```
User: "Here are my meeting notes, create tasks from them"
         │
         ▼
1. Agent calls extract_meeting_actions(meeting_notes)
   → LLM extracts decisions, action items, owners, deadlines
         │
         ▼
2. Agent presents extracted action items to user
   → Shows proposed task titles, priorities, deadlines
         │
         ▼
3. Agent calls create_task() for each action item
   → System pauses for approval (one at a time)
         │
         ▼
4. User approves each task
   → Agent creates the task, continues to next
         │
         ▼
5. Agent reports all created task IDs to user
```
