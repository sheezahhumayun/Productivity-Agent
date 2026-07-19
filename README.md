# Productivity Agent — Week 3

> AI Summer Fellowship 2026 | Visibility Bots Innovation Lab
> Track 2: NLP & AI Agents | Week 3: From RAG to Tool-Using AI Agents

A production-grade tool-using AI agent that helps you manage tasks, organise notes, plan work, and extract action items from meetings — with human approval for every write operation.

**Live demo:** https://productivity-agent-sheezah.streamlit.app *(replace with your actual URL)*

---

## Features

- **10 Tools** — task CRUD, note management, meeting extraction, work planning, weekly reports
- **Human Approval** — every write operation pauses for explicit user approval with full parameter display
- **Multi-Step Workflows** — meeting notes → tasks, daily planning, weekly review
- **Session Memory** — full conversation context preserved across multi-turn conversations
- **Execution Logging** — every agent run logged to SQLite with step-by-step tool inputs and results
- **Live Status** — granular per-step status (Thinking → Selecting tool → Executing → Response)
- **Safety Limits** — max 8 steps, 2 retries per tool, 30s tool timeout, duplicate-call detection
- **Professional UI** — sidebar stats, task browser, notes library, log viewer with expandable detail

---

## Architecture

```
User → Streamlit UI → Agent Loop → LLM (Groq / llama-3.3-70b-versatile)
                           ↓
                    Tool Registry → Database (SQLite)
                           ↓
                    Execution Logs
```

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and data flows.

---

## Tool Catalogue

| Tool | Type | Approval | Description |
|------|------|----------|-------------|
| `create_task` | WRITE | ✅ Required | Create a new task with title, priority, due date, tags |
| `list_tasks` | READ | — | Filter and list tasks by status / priority / due date / tag |
| `update_task` | WRITE | ✅ Required | Update any task field |
| `complete_task` | WRITE | ✅ Required | Mark a task completed |
| `delete_task` | WRITE | ✅ Required | Permanently delete a task |
| `save_note` | WRITE | ✅ Required | Save a new note |
| `search_notes` | READ | — | Keyword search with optional category and date range |
| `extract_meeting_actions` | READ | — | Extract decisions, action items, and questions from meeting notes |
| `generate_work_plan` | READ | — | Prioritised day plan based on pending tasks and available hours |
| `generate_weekly_report` | READ | — | Weekly productivity summary with completion stats and next-week priorities |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| LLM | Groq API — `llama-3.3-70b-versatile` |
| LLM Client | OpenAI Python SDK (Groq is OpenAI-compatible) |
| Frontend | Streamlit |
| Database | SQLite via SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Testing | pytest |
| Config | python-dotenv + `st.secrets` (Streamlit Cloud) |

---

## Installation

### Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com/keys) (free tier available)

### Local setup

```bash
# 1. Clone / navigate to the project
cd week3-productivity-agent

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Open .env and set GROQ_API_KEY=your_key_here

# 5. Run the application
streamlit run streamlit_app.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ | — | Your Groq API key |
| `LLM_MODEL` | ❌ | `llama-3.3-70b-versatile` | Model to use |
| `DB_PATH` | ❌ | `data/productivity.db` | SQLite database path |
| `LOG_DIR` | ❌ | `data/logs` | Log file directory |

---

## Streamlit Cloud Deployment

1. Push the repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app.
3. Set **Main file path** to `streamlit_app.py`.
4. Under **Secrets**, add:

```toml
GROQ_API_KEY = "gsk_..."
LLM_MODEL = "llama-3.3-70b-versatile"
```

5. Click **Deploy**. The app reads secrets via `st.secrets` automatically.

---

## Running Tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=term-missing
```

All tests use an in-memory SQLite database and do not require a live API key.

---

## Example Requests

**Task management:**
```
Show me all high-priority tasks
Create a task to review the API documentation, high priority, due 2026-08-01
Mark task #3 as complete
What tasks are overdue?
```

**Daily planning:**
```
Generate my work plan for today with 6 available hours
Show me a weekly productivity report
```

**Meeting notes:**
```
Parse these meeting notes and create tasks:
- Decided to launch v2 by end of Q3
- John will update the database schema by Friday
- Need to review security before launch
- Open question: should we add OAuth?
```

**Notes:**
```
Save a note about the API rate limits we discussed
Search my notes for information about authentication
Search notes from last week about the database
```

---

## Project Structure

```
week3-productivity-agent/
├── streamlit_app.py         # Streamlit Cloud entry point
├── app/
│   ├── main.py              # Streamlit UI (tabs: Chat, Tasks, Notes, Logs)
│   ├── config.py            # Env vars, agent limits, approval set
│   ├── agent/
│   │   ├── agent.py         # Core agent loop + approval resume + status callbacks
│   │   ├── prompts.py       # System prompt (versioned)
│   │   └── state.py         # AgentRunResult, PendingApproval, ToolCallRecord
│   ├── tools/
│   │   ├── __init__.py      # Tool registry, router, timeout enforcement
│   │   ├── task_tools.py    # 5 task management tools
│   │   ├── note_tools.py    # 2 note tools (save + search with date range)
│   │   └── planning_tools.py # 3 planning tools
│   ├── database/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── repository.py    # CRUD layer
│   └── logging/
│       └── run_logger.py    # Python logging setup
├── tests/
│   ├── test_agent.py        # 31 automated tests (no API key needed)
│   └── evaluation_dataset.py # 34 evaluation cases
├── docs/
│   ├── architecture.md      # System diagram and data flows
│   └── prompt-design.md     # System prompt documentation (Req 12)
├── data/                    # SQLite DB + logs (git-ignored)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Agent Safety

| Mechanism | Detail |
|-----------|--------|
| Approval gates | 5 write tools require explicit confirmation before execution |
| Step limit | Max 8 steps per request — prevents runaway loops |
| Retry limit | Max 2 retries per tool — stops repeated failures |
| Tool timeout | 30s hard timeout per tool call — enforced via threading |
| Duplicate detection | Identical (name + args) calls within one turn are blocked |
| Input validation | All tool inputs validated with Pydantic before execution |
| No secret exposure | API keys never shown in UI, logs, or error messages |
| Error boundaries | All tool errors caught and returned as structured results |

See [`docs/prompt-design.md`](docs/prompt-design.md) for the agent execution limit rationale.

---

## Agent Execution Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max agent steps | 8 | Enough for complex multi-step workflows; prevents runaway loops |
| Max tool retries | 2 | One automatic retry for transient failures, then surface the error |
| Tool timeout | 30 s | LLM sub-calls (extract_meeting_actions) may take 10–15 s; 30 s is safe |
| Duplicate call block | Exact (name + args) match | Prevents the model from re-calling the same tool with the same inputs |

---

## Known Limitations

1. **No semantic search** — notes search uses SQL LIKE, not vector embeddings
2. **Single user** — no authentication; designed for local single-user use
3. **Session-only memory** — conversation history resets on page refresh
4. **Sequential approval** — multiple write operations require one approval at a time
5. **Fixed effort estimates** — work plan uses 1 h (medium/high) or 2 h (critical) per task

---

## Future Roadmap

- [ ] Semantic note search with embeddings (ChromaDB / pgvector)
- [ ] Multi-user support with authentication
- [ ] Calendar integration (Google / Outlook)
- [ ] Reminder and notification system
- [ ] Batch task approval UI
- [ ] Export to PDF / Markdown
- [ ] Persistent cross-session memory
