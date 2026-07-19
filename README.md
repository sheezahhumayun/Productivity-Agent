# Productivity Agent

> AI Summer Fellowship 2026 · Visibility Bots Innovation Lab
> Track 2: NLP & AI Agents · Week 3: From RAG to Tool-Using AI Agents

A production-grade tool-using AI agent for personal productivity management:
task tracking, note-taking, meeting extraction, and daily planning — with
mandatory human approval for every write operation.

**Deployed app:** https://sheezahhumayun-productivity-agent.streamlit.app
**Demo video:** *(add link after recording)*
**GitHub:** https://github.com/sheezahhumayun/Productivity-Agent

---

## Problem Statement

Knowledge workers lose hours every week switching between task managers, note
apps, and meeting tools. The Productivity Agent provides a single conversational
interface that creates tasks from natural language, extracts action items from
meeting notes, searches saved notes, and produces prioritised daily work plans —
while always requiring explicit human approval before any data is changed.

---

## Key Features

| Feature | Detail |
|---|---|
| **10 AI tools** | Task CRUD, note management, meeting extraction, work planning, weekly reports |
| **Human approval** | Every write operation pauses for explicit approval with full parameter display |
| **Live status** | `st.status()` shows Thinking → Selecting tool → Executing → Response in real time |
| **Multi-step workflows** | Meeting notes → tasks, daily planning, weekly review |
| **Session memory** | Full conversation history passed to the LLM on every turn |
| **Execution logging** | Per-run log with tool inputs, results, approval status, timing |
| **Safety limits** | Max 8 steps, 2 retries, 30 s tool timeout, duplicate-call detection |
| **31 automated tests** | All passing; no API key required |

---

## Architecture Overview

```
User
 │
 ▼
Streamlit UI (chat / tasks / notes / logs tabs)
 │ status_fn callback for live step updates
 ▼
Agent Loop  ──────────────────────────────────────┐
 │  step limit: 8                                  │
 │  duplicate detection                            │
 ▼                                                 ▼
Groq API                               Tool Registry (10 tools)
llama-3.3-70b-versatile                 30 s timeout per call
OpenAI-compatible SDK                   Pydantic input validation
 │                                                 │
 └─────────────────┬─────────────────────────────-─┘
                   ▼
          SQLite via SQLAlchemy
          tasks · notes · execution_logs
```

**Human approval flow:** when the loop encounters a write tool, it returns a
`PendingApproval` object to Streamlit. An approval card is displayed showing the
tool name, human description, and full JSON parameters. The loop resumes after the
user clicks Approve or Reject.

Full details: [`docs/architecture.md`](docs/architecture.md)

---

## Tool Catalogue

| Tool | Type | Approval | Description |
|---|---|---|---|
| `create_task` | WRITE | ✅ | Create a task with title, priority, due date, tags |
| `list_tasks` | READ | — | Filter tasks by status / priority / due date / tag |
| `update_task` | WRITE | ✅ | Modify any task field |
| `complete_task` | WRITE | ✅ | Mark a task completed |
| `delete_task` | WRITE | ✅ | Permanently delete a task |
| `save_note` | WRITE | ✅ | Save a note with category and tags |
| `search_notes` | READ | — | Keyword search with optional category and date range |
| `extract_meeting_actions` | READ | — | LLM-powered meeting note analysis |
| `generate_work_plan` | READ | — | Prioritised daily schedule from pending tasks |
| `generate_weekly_report` | READ | — | Weekly productivity summary |

Full input/output schemas: [`docs/tool-specifications.md`](docs/tool-specifications.md)

---

## Technology Stack

| Component | Technology |
|---|---|
| LLM | Groq API — `llama-3.3-70b-versatile` |
| LLM Client | OpenAI Python SDK (Groq is OpenAI-compatible) |
| Frontend | Streamlit |
| Database | SQLite via SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-cov |
| Config | python-dotenv + `st.secrets` |
| Deployment | Streamlit Community Cloud |

---

## Installation

### Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com/keys) (free tier, no credit card)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/sheezahhumayun/Productivity-Agent.git
cd Productivity-Agent

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env and set:  GROQ_API_KEY=gsk_...
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | — | Your Groq API key (get one at console.groq.com) |
| `LLM_MODEL` | ❌ | `llama-3.3-70b-versatile` | Model to use |
| `DB_PATH` | ❌ | `data/productivity.db` | SQLite database file path |
| `LOG_DIR` | ❌ | `data/logs` | Application log directory |

---

## How to Run Locally

```bash
streamlit run streamlit_app.py
```

The app opens at http://localhost:8501. The sidebar shows "✅ API Key configured"
when the key is loaded correctly.

---

## How to Run Tests

```bash
# Run the full test suite (no API key required)
pytest tests/test_agent.py -v

# With coverage report
pytest tests/test_agent.py -v --cov=app --cov-report=term-missing

# Run the evaluation dataset (tool-level tests only, no API key)
python tests/evaluation_dataset.py
```

Expected output:
```
31 passed in 11.57s
Tool-level evaluation: 15/15 passed
```

---

## Example User Requests

### Task management
```
Show me all high-priority tasks
Create a task: Review API docs, high priority, due 2026-08-01
Mark task #3 as complete
What tasks are overdue?
Delete task #5
```

### Daily planning
```
Generate my work plan for today with 6 available hours
Show me the weekly productivity report
```

### Meeting notes → tasks
```
Extract tasks from these meeting notes:
- Decided to launch v2 by end of Q3
- John will update the DB schema by Friday
- Need to review security before launch
- Open question: should we add OAuth?
```

### Notes
```
Save a note about the API rate limits we discussed
Search my notes for authentication
Find notes from last week about the database schema
```

---

## Evaluation Results

Results from running the 34-case evaluation dataset:

| Metric | Target | Result |
|---|---|---|
| Tool selection accuracy | ≥ 85% | **91%** (31/34) |
| Argument accuracy | ≥ 80% | **88%** (30/34) |
| Task completion rate | ≥ 80% | **91%** |
| Approval compliance | 100% | **100%** (17/17 cases) |
| Invalid action rate | < 10% | **6%** |
| Average response time | — | **4.2 s/turn** |
| Automated test pass rate | — | **31/31 (100%)** |
| Tool unit test pass rate | — | **15/15 (100%)** |

Full evaluation details: [`docs/evaluation-dataset.md`](docs/evaluation-dataset.md)

---

## Screenshots

See [`screenshots/`](screenshots/) for application screenshots.

*Key screens: chat interface with live status, approval card, task panel with filters, execution logs with expandable tool detail.*

---

## Deployment

### Streamlit Community Cloud

1. Fork / push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app.
3. Set **Repository** and **Main file path** to `streamlit_app.py`.
4. Under **Advanced → Secrets**, add:

```toml
GROQ_API_KEY = "gsk_your_key_here"
LLM_MODEL = "llama-3.3-70b-versatile"
```

5. Click **Deploy**.

> **Note on data persistence:** Streamlit Cloud uses an ephemeral filesystem.
> The SQLite database does not persist between app restarts. For persistent data,
> use a managed database (e.g., Supabase PostgreSQL) and update `DB_PATH`.

---

## Project Structure

```
week3-productivity-agent/
├── streamlit_app.py              # Streamlit Cloud entry point
├── app/
│   ├── main.py                   # UI: chat, tasks, notes, logs tabs
│   ├── config.py                 # Env vars and agent limits
│   ├── agent/
│   │   ├── agent.py              # Core loop + approval resume + status callbacks
│   │   ├── prompts.py            # System prompt (versioned)
│   │   └── state.py              # AgentRunResult, PendingApproval, ToolCallRecord
│   ├── tools/
│   │   ├── __init__.py           # Router, whitelist, 30 s timeout enforcement
│   │   ├── task_tools.py         # 5 task tools with Pydantic validation
│   │   ├── note_tools.py         # 2 note tools (save + search with date range)
│   │   └── planning_tools.py     # 3 planning tools
│   ├── database/
│   │   ├── models.py             # SQLAlchemy ORM models (3 tables)
│   │   └── repository.py         # Full CRUD layer
│   └── logging/
│       └── run_logger.py         # Python logging configuration
├── tests/
│   ├── test_agent.py             # 31 automated tests
│   └── evaluation_dataset.py     # 34 evaluation cases + 15 tool unit tests
├── docs/
│   ├── agent-design.md           # Assignment 2: Design document
│   ├── architecture.md           # Assignment 3: Diagram + explanations
│   ├── tool-specifications.md    # Assignment 4: Full tool specs
│   ├── evaluation-dataset.md     # Assignment 5: Test cases + results
│   ├── experiments.md            # Assignment 6: 6 experiments
│   ├── security-review.md        # Assignment 7: 10 security risks
│   ├── builder-journal.md        # Assignment 8: Reflection
│   └── prompt-design.md          # Requirement 12: Prompt documentation
├── screenshots/                  # Application screenshots
├── .env.example                  # Environment variable template
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Agent Execution Limits

| Limit | Value | Rationale |
|---|---|---|
| Max agent steps | 8 | Covers all tested workflows (avg 4.1 steps used); prevents loops |
| Max tool retries | 2 | One retry for transient errors; avoids wasted API calls |
| Tool timeout | 30 s | LLM sub-calls take 10–15 s; 30 s is a safe hard limit |
| Duplicate call block | Exact name+args match | Prevents the model from looping on identical reads |

---

## Known Limitations

1. **No semantic search** — notes search uses SQL LIKE, not vector embeddings
2. **Single user** — no authentication; designed for local single-user use
3. **Session-only memory** — conversation history resets on page refresh
4. **Ephemeral data on Streamlit Cloud** — SQLite is lost between deployments
5. **Sequential approval** — multiple write operations require one approval at a time
6. **Fixed effort estimates** — work plan uses 1 h per medium/high task, 2 h for critical

---

## Future Roadmap

- [ ] Persistent cross-session memory with conversation history in database
- [ ] Streaming output (token-by-token response display)
- [ ] Semantic note search with sentence embeddings (ChromaDB)
- [ ] Calendar integration (Google / Outlook)
- [ ] Batch approval UI for multiple tasks at once
- [ ] Export to PDF / Markdown report
- [ ] Multi-user support with authentication
- [ ] LangGraph refactor for more complex approval state machines

---

## Documentation

| Document | Location |
|---|---|
| Agent design document | [`docs/agent-design.md`](docs/agent-design.md) |
| Architecture diagram | [`docs/architecture.md`](docs/architecture.md) |
| Tool specifications | [`docs/tool-specifications.md`](docs/tool-specifications.md) |
| Evaluation dataset | [`docs/evaluation-dataset.md`](docs/evaluation-dataset.md) |
| Experiments report | [`docs/experiments.md`](docs/experiments.md) |
| Security review | [`docs/security-review.md`](docs/security-review.md) |
| Builder journal | [`docs/builder-journal.md`](docs/builder-journal.md) |
| Prompt design | [`docs/prompt-design.md`](docs/prompt-design.md) |
