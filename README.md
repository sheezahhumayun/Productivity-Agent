# Productivity Agent — Week 3

> AI Summer Fellowship 2026 | Visibility Bots Innovation Lab  
> Track 2: NLP & AI Agents | Week 3: From RAG to Tool-Using AI Agents

A production-grade tool-using AI agent that helps you manage tasks, organize notes, plan work, and extract action items from meetings — with human approval for every write operation.

---

## Features

- **10 Tools** — task CRUD, note management, meeting extraction, work planning, weekly reports
- **Human Approval** — every write operation pauses for explicit user approval
- **Multi-Step Workflows** — meeting notes → tasks, daily planning, weekly review
- **Session Memory** — context preserved across multi-turn conversations
- **Execution Logging** — every agent run logged to SQLite with step-by-step details
- **Step Limits** — max 8 steps per request, 2 retries per tool
- **Professional UI** — Streamlit with sidebar stats, task browser, notes library, log viewer

---

## Architecture

```
User → Streamlit UI → Agent Controller → LLM (Claude)
                            ↓
                    Tool Registry → Database (SQLite)
                            ↓
                    Execution Logs
```

See [`docs/architecture.md`](docs/architecture.md) for the full diagram.

---

## Tool Catalogue

| Tool | Type | Approval | Description |
|------|------|----------|-------------|
| `create_task` | WRITE | ✅ Required | Create a new task |
| `list_tasks` | READ | ❌ None | Filter and list tasks |
| `update_task` | WRITE | ✅ Required | Update task fields |
| `complete_task` | WRITE | ✅ Required | Mark task completed |
| `delete_task` | WRITE | ✅ Required | Permanently delete task |
| `save_note` | WRITE | ✅ Required | Save a new note |
| `search_notes` | READ | ❌ None | Keyword search notes |
| `extract_meeting_actions` | READ | ❌ None | Extract decisions & action items from meeting notes |
| `generate_work_plan` | READ | ❌ None | Create a prioritized day plan |
| `generate_weekly_report` | READ | ❌ None | Weekly productivity summary |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| LLM | Anthropic Claude (claude-haiku-4-5) |
| Frontend | Streamlit |
| Database | SQLite via SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Testing | pytest |
| Config | python-dotenv |

---

## Installation

### Prerequisites
- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Steps

```bash
# 1. Clone / navigate to the project
cd week3-productivity-agent

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 5. Run the application
streamlit run app/main.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | — | Your Anthropic API key |
| `LLM_MODEL` | ❌ | `claude-haiku-4-5-20251001` | Model to use |
| `DB_PATH` | ❌ | `data/productivity.db` | SQLite database path |
| `LOG_DIR` | ❌ | `data/logs` | Log file directory |

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected output: 25+ tests, all passing (no API key needed for tests).

---

## Example Requests

**Task management:**
- "Show me all high-priority tasks"
- "Create a task to review the API documentation, high priority, due 2026-08-01"
- "Mark task #3 as complete"
- "What tasks are overdue?"

**Planning:**
- "Generate my work plan for today with 6 available hours"
- "Show me a weekly productivity report"

**Meeting notes:**
```
Parse these meeting notes and create tasks:
- Decided to launch v2 by end of Q3
- John will update the database schema by Friday  
- Need to review security before launch
- Open question: should we add OAuth?
```

**Notes:**
- "Save a note about the API rate limits we discussed"
- "Search my notes for information about authentication"

---

## Project Structure

```
week3-productivity-agent/
├── app/
│   ├── main.py              # Streamlit UI entry point
│   ├── config.py            # Environment and constants
│   ├── agent/
│   │   ├── agent.py         # Core agent loop + approval resume
│   │   ├── prompts.py       # System prompt
│   │   └── state.py         # AgentRunResult, PendingApproval
│   ├── tools/
│   │   ├── __init__.py      # Tool registry + router
│   │   ├── task_tools.py    # 5 task management tools
│   │   ├── note_tools.py    # 2 note tools
│   │   └── planning_tools.py # 3 planning tools
│   ├── database/
│   │   ├── models.py        # SQLAlchemy models
│   │   └── repository.py    # All DB operations
│   └── logging/
│       └── run_logger.py    # Logging setup
├── tests/
│   └── test_agent.py        # 25+ automated tests
├── data/                    # SQLite DB + logs (git-ignored)
├── docs/
│   └── architecture.md      # Architecture diagram + flow
├── .env.example
├── requirements.txt
└── README.md
```

---

## Agent Safety

- **Approval gates** — 5 write tools require explicit user confirmation
- **Step limits** — max 8 steps per request prevents infinite loops
- **Retry limits** — max 2 retries per tool prevents runaway calls
- **Input validation** — all tool inputs validated with Pydantic before execution
- **No secret exposure** — API keys never shown in UI or logs
- **Error boundaries** — all tool errors caught and returned gracefully

---

## Known Limitations

1. **No semantic search** — notes search uses SQL LIKE (not vector embeddings)
2. **Single user** — no authentication; designed for local single-user use
3. **Session-only memory** — conversation history resets on page refresh
4. **Sequential approval** — multiple write operations require one approval at a time
5. **Work estimates** — plan tool uses fixed 1-hour estimates per task

---

## Future Roadmap

- [ ] Semantic note search with embeddings (ChromaDB)
- [ ] Multi-user support with auth
- [ ] Calendar integration (Google/Outlook)
- [ ] Reminder/notification system
- [ ] Batch task approval UI
- [ ] Export to PDF/Markdown
- [ ] LangGraph state machine for more complex workflows
