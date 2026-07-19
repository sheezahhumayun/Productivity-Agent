"""
Automated test suite for the Productivity Agent.
Run with: pytest tests/ -v
"""
import os
import sys
import pytest
import tempfile

# Use a temp database for all tests
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
# Prevent real API calls in most tests
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key_placeholder")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.models import init_db
from app.database import repository as repo
from app.tools.task_tools import execute_task_tool, CreateTaskInput, UpdateTaskInput
from app.tools.note_tools import execute_note_tool, SaveNoteInput
from app.agent.state import new_run_id, PendingApproval, ToolCallRecord
from app.config import APPROVAL_REQUIRED_TOOLS


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the test database before each test."""
    init_db()
    from app.database.models import get_engine, Base
    engine = get_engine()
    # Drop and recreate all tables for a clean slate
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


# ── Task creation tests ────────────────────────────────────────────────────────

class TestTaskCreation:
    def test_create_basic_task(self):
        result = execute_task_tool("create_task", {"title": "Write tests"})
        assert result["success"] is True
        assert result["task"]["title"] == "Write tests"
        assert result["task"]["status"] == "pending"
        assert result["task"]["priority"] == "medium"
        assert result["task"]["id"] > 0

    def test_create_task_with_all_fields(self):
        result = execute_task_tool("create_task", {
            "title": "Deploy API",
            "description": "Deploy the REST API to production",
            "priority": "high",
            "due_date": "2026-08-01",
            "tags": ["backend", "deploy"],
        })
        assert result["success"] is True
        task = result["task"]
        assert task["priority"] == "high"
        assert task["due_date"] == "2026-08-01"
        assert "backend" in task["tags"]

    def test_create_task_invalid_priority_raises(self):
        with pytest.raises(Exception):
            CreateTaskInput(title="Test", priority="ultra")

    def test_create_task_missing_title_raises(self):
        with pytest.raises(Exception):
            execute_task_tool("create_task", {"priority": "high"})


# ── Task listing tests ─────────────────────────────────────────────────────────

class TestTaskListing:
    def test_list_all_tasks(self):
        repo.create_task("Task A", priority="high")
        repo.create_task("Task B", priority="low")
        result = execute_task_tool("list_tasks", {})
        assert result["success"] is True
        assert result["count"] >= 2

    def test_list_tasks_filter_by_priority(self):
        repo.create_task("Critical task", priority="critical")
        repo.create_task("Low task", priority="low")
        result = execute_task_tool("list_tasks", {"priority": "critical"})
        assert result["success"] is True
        assert all(t["priority"] == "critical" for t in result["tasks"])

    def test_list_tasks_filter_by_status(self):
        repo.create_task("Pending task", priority="medium")
        task = repo.create_task("Done task", priority="medium")
        repo.complete_task(task["id"])
        result = execute_task_tool("list_tasks", {"status": "pending"})
        assert result["success"] is True
        assert all(t["status"] == "pending" for t in result["tasks"])

    def test_list_tasks_empty_db(self):
        result = execute_task_tool("list_tasks", {})
        assert result["success"] is True
        assert result["count"] == 0

    def test_list_tasks_filter_by_tag(self):
        repo.create_task("Tagged", tags=["dev", "urgent"])
        repo.create_task("Untagged")
        result = execute_task_tool("list_tasks", {"tag": "dev"})
        assert result["success"] is True
        assert result["count"] >= 1
        assert all("dev" in t["tags"] for t in result["tasks"])


# ── Task update tests ──────────────────────────────────────────────────────────

class TestTaskUpdates:
    def test_update_task_priority(self):
        task = repo.create_task("Updateable task", priority="low")
        result = execute_task_tool("update_task", {
            "task_id": task["id"],
            "priority": "high",
        })
        assert result["success"] is True
        assert result["task"]["priority"] == "high"

    def test_update_task_status(self):
        task = repo.create_task("Status test")
        result = execute_task_tool("update_task", {
            "task_id": task["id"],
            "status": "in_progress",
        })
        assert result["success"] is True
        assert result["task"]["status"] == "in_progress"

    def test_update_invalid_task_id(self):
        result = execute_task_tool("update_task", {"task_id": 99999})
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_update_invalid_status_raises(self):
        task = repo.create_task("Test task")
        with pytest.raises(Exception):
            UpdateTaskInput(task_id=task["id"], status="flying")


# ── Task completion tests ──────────────────────────────────────────────────────

class TestTaskCompletion:
    def test_complete_task(self):
        task = repo.create_task("Complete me")
        result = execute_task_tool("complete_task", {"task_id": task["id"]})
        assert result["success"] is True
        assert result["task"]["status"] == "completed"

    def test_complete_nonexistent_task(self):
        result = execute_task_tool("complete_task", {"task_id": 99999})
        assert result["success"] is False

    def test_complete_already_completed_task(self):
        task = repo.create_task("Done already")
        repo.complete_task(task["id"])
        # Completing again should still work (idempotent)
        result = execute_task_tool("complete_task", {"task_id": task["id"]})
        assert result["success"] is True


# ── Notes tests ────────────────────────────────────────────────────────────────

class TestNotes:
    def test_save_note(self):
        result = execute_note_tool("save_note", {
            "title": "Meeting notes",
            "content": "Discussed project timeline",
            "category": "meeting",
            "tags": ["q3", "planning"],
        })
        assert result["success"] is True
        assert result["note"]["id"] > 0
        assert result["note"]["title"] == "Meeting notes"

    def test_save_note_missing_content_raises(self):
        with pytest.raises(Exception):
            SaveNoteInput(title="No content")

    def test_search_notes_found(self):
        repo.save_note("API Docs", "How to use the REST API endpoints")
        result = execute_note_tool("search_notes", {"query": "REST API"})
        assert result["success"] is True
        assert result["count"] >= 1

    def test_search_notes_not_found(self):
        result = execute_note_tool("search_notes", {"query": "xyzzy_nonexistent_term_12345"})
        assert result["success"] is True
        assert result["count"] == 0

    def test_search_notes_by_category(self):
        repo.save_note("Meeting 1", "Notes from team standup", category="meeting")
        repo.save_note("Idea 1", "Product feature ideas", category="ideas")
        result = execute_note_tool("search_notes", {"query": "Notes", "category": "meeting"})
        assert result["success"] is True
        assert all(n.get("category") == "meeting" for n in result["notes"])


# ── Approval enforcement tests ─────────────────────────────────────────────────

class TestApprovalEnforcement:
    def test_write_tools_require_approval(self):
        write_tools = ["create_task", "update_task", "complete_task", "delete_task", "save_note"]
        for tool in write_tools:
            assert tool in APPROVAL_REQUIRED_TOOLS, f"{tool} must require approval"

    def test_read_tools_do_not_require_approval(self):
        read_tools = ["list_tasks", "search_notes", "generate_work_plan", "generate_weekly_report"]
        for tool in read_tools:
            assert tool not in APPROVAL_REQUIRED_TOOLS, f"{tool} should NOT require approval"


# ── Database persistence tests ────────────────────────────────────────────────

class TestDatabasePersistence:
    def test_task_persists_after_creation(self):
        created = repo.create_task("Persistent task", priority="high")
        fetched = repo.get_task(created["id"])
        assert fetched is not None
        assert fetched["title"] == "Persistent task"
        assert fetched["priority"] == "high"

    def test_task_delete(self):
        task = repo.create_task("Delete me")
        deleted = repo.delete_task(task["id"])
        assert deleted is True
        fetched = repo.get_task(task["id"])
        assert fetched is None

    def test_delete_nonexistent_task(self):
        result = repo.delete_task(99999)
        assert result is False


# ── Agent state tests ─────────────────────────────────────────────────────────

class TestAgentState:
    def test_run_id_format(self):
        rid = new_run_id()
        assert rid.startswith("run_")
        assert len(rid) == 12  # "run_" + 8 hex chars

    def test_run_id_unique(self):
        ids = {new_run_id() for _ in range(20)}
        assert len(ids) == 20

    def test_pending_approval_stores_all_fields(self):
        record = ToolCallRecord(step=1, tool_name="create_task", tool_id="id1", tool_input={"title": "X"})
        pa = PendingApproval(
            run_id="run_abc12345",
            log_id=1,
            tool_use_id="id1",
            tool_name="create_task",
            tool_input={"title": "X"},
            messages=[],
            step_count=1,
            tool_calls_log=[record],
            human_description='Create task "X"',
        )
        assert pa.tool_name == "create_task"
        assert pa.step_count == 1
        assert len(pa.tool_calls_log) == 1


# ── Max step limit test ───────────────────────────────────────────────────────

class TestMaxStepLimit:
    def test_max_steps_config(self):
        from app.config import MAX_AGENT_STEPS
        assert MAX_AGENT_STEPS == 8

    def test_max_retries_config(self):
        from app.config import MAX_TOOL_RETRIES
        assert MAX_TOOL_RETRIES == 2
