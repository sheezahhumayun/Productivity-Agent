# Tool Specifications — Productivity Agent

> Assignment 4 | AI Summer Fellowship 2026 | Week 3

This document defines every tool registered in the agent. Each specification is
complete enough for an independent developer to re-implement the tool without
reading the source code.

---

## Tool 1 — `create_task`

| Field | Value |
|---|---|
| **Purpose** | Create a new task and persist it to the database |
| **Operation** | WRITE |
| **Approval required** | ✅ Yes |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "title":       { "type": "string",  "description": "Short, clear task title" },
    "description": { "type": "string",  "description": "Detailed description" },
    "priority":    { "type": "string",  "enum": ["low","medium","high","critical"] },
    "due_date":    { "type": "string",  "description": "YYYY-MM-DD format" },
    "tags":        { "type": "array", "items": {"type": "string"} }
  },
  "required": ["title"]
}
```

| Field | Required | Default | Notes |
|---|---|---|---|
| `title` | ✅ | — | 1–500 characters |
| `description` | ❌ | null | Free text |
| `priority` | ❌ | `"medium"` | Must be one of the enum values |
| `due_date` | ❌ | null | ISO date string YYYY-MM-DD |
| `tags` | ❌ | `[]` | Array of lowercase strings |

### Output schema

```json
{
  "success": true,
  "task": {
    "id": 7,
    "title": "Review API docs",
    "description": null,
    "priority": "high",
    "status": "pending",
    "due_date": "2026-08-01",
    "tags": ["backend"],
    "source": null,
    "notes": null,
    "created_at": "2026-07-20 10:00:00",
    "updated_at": "2026-07-20 10:00:00"
  },
  "message": "Task #7 created: Review API docs"
}
```

### Possible errors

| Error | Cause |
|---|---|
| `"priority must be one of {'low', 'medium', 'high', 'critical'}"` | Pydantic validation failure |
| `"field required: title"` | Title missing from input |

### Example call

```json
{
  "tool": "create_task",
  "input": {
    "title": "Review API docs",
    "priority": "high",
    "due_date": "2026-08-01",
    "tags": ["backend", "docs"]
  }
}
```

### Example result

```json
{
  "success": true,
  "task": {"id": 7, "title": "Review API docs", "priority": "high", "status": "pending"},
  "message": "Task #7 created: Review API docs"
}
```

---

## Tool 2 — `list_tasks`

| Field | Value |
|---|---|
| **Purpose** | Retrieve tasks from the database with optional filters |
| **Operation** | READ |
| **Approval required** | ❌ No |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "status":     { "type": "string", "enum": ["pending","in_progress","blocked","completed","cancelled"] },
    "priority":   { "type": "string", "enum": ["low","medium","high","critical"] },
    "due_before": { "type": "string", "description": "Return tasks with due_date ≤ this date (YYYY-MM-DD)" },
    "tag":        { "type": "string", "description": "Return tasks containing this tag" }
  },
  "required": []
}
```

All fields are optional. Omitting all fields returns up to 50 tasks ordered by creation date descending.

### Output schema

```json
{
  "success": true,
  "tasks": [ /* array of task objects */ ],
  "count": 3
}
```

### Possible errors

| Error | Cause |
|---|---|
| `"status must be one of {...}"` | Invalid status string |

### Example call

```json
{"tool": "list_tasks", "input": {"priority": "critical", "due_before": "2026-08-01"}}
```

### Example result

```json
{
  "success": true,
  "tasks": [
    {"id": 4, "title": "Security review", "priority": "critical", "status": "pending", "due_date": "2026-07-25"}
  ],
  "count": 1
}
```

---

## Tool 3 — `update_task`

| Field | Value |
|---|---|
| **Purpose** | Modify one or more fields of an existing task |
| **Operation** | WRITE |
| **Approval required** | ✅ Yes |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "task_id":     { "type": "integer" },
    "title":       { "type": "string" },
    "description": { "type": "string" },
    "priority":    { "type": "string", "enum": ["low","medium","high","critical"] },
    "due_date":    { "type": "string" },
    "status":      { "type": "string", "enum": ["pending","in_progress","blocked","completed","cancelled"] },
    "tags":        { "type": "array", "items": {"type": "string"} },
    "notes":       { "type": "string" }
  },
  "required": ["task_id"]
}
```

| Field | Required | Notes |
|---|---|---|
| `task_id` | ✅ | Integer ID from `list_tasks` |
| All others | ❌ | Only provided fields are updated; others unchanged |

### Output schema

```json
{
  "success": true,
  "task": { /* full updated task object */ },
  "message": "Task #4 updated"
}
```

### Possible errors

| Error | Cause |
|---|---|
| `"Task #N not found"` | task_id does not exist in database |
| Pydantic validation errors | Invalid priority or status enum value |

### Example call

```json
{"tool": "update_task", "input": {"task_id": 4, "priority": "critical", "status": "in_progress"}}
```

---

## Tool 4 — `complete_task`

| Field | Value |
|---|---|
| **Purpose** | Mark a task as completed (sets status to "completed") |
| **Operation** | WRITE |
| **Approval required** | ✅ Yes |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "task_id": { "type": "integer", "description": "ID of the task to mark complete" }
  },
  "required": ["task_id"]
}
```

### Output schema

```json
{
  "success": true,
  "task": { "id": 4, "status": "completed", "updated_at": "2026-07-20 14:30:00" },
  "message": "Task #4 marked as completed"
}
```

### Possible errors

| Error | Cause |
|---|---|
| `"Task #N not found"` | task_id does not exist |

### Example call

```json
{"tool": "complete_task", "input": {"task_id": 4}}
```

---

## Tool 5 — `delete_task`

| Field | Value |
|---|---|
| **Purpose** | Permanently remove a task from the database (irreversible) |
| **Operation** | WRITE |
| **Approval required** | ✅ Yes |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "task_id": { "type": "integer" }
  },
  "required": ["task_id"]
}
```

### Output schema

```json
{"success": true, "message": "Task #4 permanently deleted"}
```

### Possible errors

| Error | Cause |
|---|---|
| `"Task #N not found"` | task_id does not exist |

---

## Tool 6 — `save_note`

| Field | Value |
|---|---|
| **Purpose** | Save a new note to the database |
| **Operation** | WRITE |
| **Approval required** | ✅ Yes |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "title":    { "type": "string" },
    "content":  { "type": "string" },
    "category": { "type": "string", "description": "e.g. meeting, research, ideas, reference" },
    "tags":     { "type": "array", "items": {"type": "string"} }
  },
  "required": ["title", "content"]
}
```

| Field | Required | Notes |
|---|---|---|
| `title` | ✅ | 1–500 characters |
| `content` | ✅ | Full note text, any length |
| `category` | ❌ | Free-form category string |
| `tags` | ❌ | Array of strings |

### Output schema

```json
{
  "success": true,
  "note": {
    "id": 3,
    "title": "Sprint Review",
    "content": "...",
    "category": "meeting",
    "tags": ["q3"],
    "created_at": "2026-07-20 10:00:00",
    "updated_at": "2026-07-20 10:00:00"
  },
  "message": "Note #3 saved: Sprint Review"
}
```

### Possible errors

| Error | Cause |
|---|---|
| `"field required: content"` | Content missing |

---

## Tool 7 — `search_notes`

| Field | Value |
|---|---|
| **Purpose** | Search notes by keyword in title or content |
| **Operation** | READ |
| **Approval required** | ❌ No |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "query":     { "type": "string", "description": "Keyword or phrase to search for" },
    "category":  { "type": "string", "description": "Filter by category" },
    "date_from": { "type": "string", "description": "Filter notes created on or after YYYY-MM-DD" },
    "date_to":   { "type": "string", "description": "Filter notes created on or before YYYY-MM-DD" }
  },
  "required": ["query"]
}
```

### Output schema

```json
{
  "success": true,
  "notes": [ /* array of note objects, ordered by updated_at descending */ ],
  "count": 2
}
```

Returns an empty list (count=0) when no notes match. This is a success, not an error.

### Example call

```json
{"tool": "search_notes", "input": {"query": "authentication", "date_from": "2026-07-01"}}
```

---

## Tool 8 — `extract_meeting_actions`

| Field | Value |
|---|---|
| **Purpose** | Analyse meeting notes with the LLM to extract structured decisions, action items, and unresolved questions |
| **Operation** | READ (LLM sub-call, no database write) |
| **Approval required** | ❌ No |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "meeting_notes": { "type": "string", "description": "Raw meeting notes or transcript" },
    "meeting_title": { "type": "string", "description": "Optional title for context" }
  },
  "required": ["meeting_notes"]
}
```

### Output schema

```json
{
  "success": true,
  "extraction": {
    "summary": "2-3 sentence meeting summary",
    "decisions": ["Decision 1", "Decision 2"],
    "action_items": [
      {
        "task": "What needs to be done",
        "owner": "Person responsible or 'Unassigned'",
        "deadline": "2026-08-01 or null",
        "priority": "high"
      }
    ],
    "unresolved_questions": ["Open question 1"],
    "participants": ["Alice", "Bob"]
  }
}
```

### Possible errors

| Error | Cause |
|---|---|
| `"Extraction failed: ..."` | LLM API error or JSON parse failure |

### Example call

```json
{
  "tool": "extract_meeting_actions",
  "input": {
    "meeting_notes": "Team decided to launch v2 by Aug 15. John will fix the login bug by Friday.",
    "meeting_title": "Sprint Planning"
  }
}
```

### Example result

```json
{
  "success": true,
  "extraction": {
    "summary": "The team committed to a v2 launch date of August 15. John owns the login bug fix.",
    "decisions": ["Launch v2 by August 15"],
    "action_items": [
      {"task": "Fix the login bug", "owner": "John", "deadline": "2026-07-25", "priority": "high"}
    ],
    "unresolved_questions": []
  }
}
```

---

## Tool 9 — `generate_work_plan`

| Field | Value |
|---|---|
| **Purpose** | Generate a prioritised daily schedule from open tasks |
| **Operation** | READ (algorithmic, no LLM sub-call) |
| **Approval required** | ❌ No |

### Input schema

```json
{
  "type": "object",
  "properties": {
    "available_hours": { "type": "number", "description": "Total working hours (default 8)" },
    "date":           { "type": "string", "description": "YYYY-MM-DD (default today)" },
    "priorities":     { "type": "array", "items": {"type": "string"}, "description": "Focus tags" }
  },
  "required": []
}
```

### Scoring algorithm

Each task receives a base score from its priority (`critical`=4, `high`=3,
`medium`=2, `low`=1). Bonuses: +2 if overdue, +1 if due today, +1 if any tag
matches user priorities. Penalty: -1 if blocked. Tasks are sorted descending by
score, then scheduled in order until the hour budget is exhausted.

Effort estimates: `critical` = 2 h, all others = 1 h.

### Output schema

```json
{
  "success": true,
  "plan": {
    "date": "2026-07-20",
    "available_hours": 6.0,
    "hours_scheduled": 5.0,
    "scheduled_tasks": [ /* tasks with estimated_hours field added */ ],
    "deferred_tasks":  [ /* tasks that didn't fit */ ],
    "recommended_focus": ["Task title 1", "Task title 2", "Task title 3"],
    "risk_warnings": ["Task #4 is OVERDUE (due 2026-07-18)"],
    "summary": "Plan for 2026-07-20: 4 tasks scheduled (5.0h), 2 deferred."
  }
}
```

---

## Tool 10 — `generate_weekly_report`

| Field | Value |
|---|---|
| **Purpose** | Produce a weekly productivity summary with statistics and next-week priorities |
| **Operation** | READ (database aggregation, no LLM sub-call) |
| **Approval required** | ❌ No |

### Input schema

```json
{"type": "object", "properties": {}, "required": []}
```

No input required. Uses current date automatically.

### Output schema

```json
{
  "success": true,
  "report": {
    "week_start": "2026-07-14",
    "report_date": "2026-07-20",
    "statistics": {
      "total_tasks": 25,
      "completed": 8,
      "in_progress": 3,
      "pending": 12,
      "blocked": 2,
      "overdue": 1
    },
    "completed_tasks":      [ /* up to 10 task objects */ ],
    "overdue_tasks":        [ /* all overdue tasks */ ],
    "blocked_tasks":        [ /* all blocked tasks */ ],
    "next_week_priorities": [ /* top 5 high/critical open tasks */ ],
    "summary": "This week: 8 completed, 1 overdue, 2 blocked. 12 tasks pending."
  }
}
```

---

## Summary Table

| # | Tool | Type | Approval | Required Inputs | Primary Output |
|---|---|---|---|---|---|
| 1 | `create_task` | WRITE | ✅ | title | Created task object |
| 2 | `list_tasks` | READ | ❌ | (none) | Filtered task list |
| 3 | `update_task` | WRITE | ✅ | task_id | Updated task object |
| 4 | `complete_task` | WRITE | ✅ | task_id | Task with status=completed |
| 5 | `delete_task` | WRITE | ✅ | task_id | Success confirmation |
| 6 | `save_note` | WRITE | ✅ | title, content | Created note object |
| 7 | `search_notes` | READ | ❌ | query | Matching note list |
| 8 | `extract_meeting_actions` | READ | ❌ | meeting_notes | Structured extraction |
| 9 | `generate_work_plan` | READ | ❌ | (none) | Prioritised schedule |
| 10 | `generate_weekly_report` | READ | ❌ | (none) | Weekly statistics |
