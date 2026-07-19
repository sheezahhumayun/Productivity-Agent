import json
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
from openai import OpenAI

from app.config import API_KEY, LLM_BASE_URL, LLM_MODEL
from app.database import repository as repo

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=API_KEY, base_url=LLM_BASE_URL)
    return _client


class ExtractMeetingInput(BaseModel):
    meeting_notes: str
    meeting_title: Optional[str] = None


class GenerateWorkPlanInput(BaseModel):
    available_hours: float = 8.0
    date: Optional[str] = None
    priorities: Optional[List[str]] = None


PLANNING_TOOL_DEFS = [
    {
        "name": "extract_meeting_actions",
        "description": (
            "Analyze meeting notes or transcripts to extract a structured summary: "
            "decisions made, action items with owners and deadlines, and unresolved questions. "
            "Does NOT require approval. Results can be used to create tasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_notes": {
                    "type": "string",
                    "description": "Raw meeting notes or transcript to analyze",
                },
                "meeting_title": {
                    "type": "string",
                    "description": "Optional title or context for the meeting",
                },
            },
            "required": ["meeting_notes"],
        },
    },
    {
        "name": "generate_work_plan",
        "description": (
            "Generate a prioritized work plan for a given day based on pending tasks. "
            "Considers priority, due dates, and available hours. "
            "Does NOT require approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "available_hours": {
                    "type": "number",
                    "description": "Total working hours available (default 8)",
                },
                "date": {
                    "type": "string",
                    "description": "Date for the plan in YYYY-MM-DD format (default: today)",
                },
                "priorities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "User-specified priority areas or tags to focus on",
                },
            },
            "required": [],
        },
    },
    {
        "name": "generate_weekly_report",
        "description": (
            "Generate a weekly productivity summary showing completed tasks, "
            "overdue tasks, blocked items, and recommendations for the next week. "
            "Does NOT require approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def _extract_with_llm(meeting_notes: str, meeting_title: Optional[str]) -> dict:
    prompt = f"""Analyze these meeting notes and extract structured information.

Meeting Title: {meeting_title or "Untitled Meeting"}

Meeting Notes:
{meeting_notes}

Return a JSON object with this exact structure:
{{
  "summary": "2-3 sentence summary of the meeting",
  "decisions": ["decision 1", "decision 2"],
  "action_items": [
    {{
      "task": "what needs to be done",
      "owner": "person responsible (or 'Unassigned')",
      "deadline": "date if mentioned, else null",
      "priority": "high/medium/low"
    }}
  ],
  "unresolved_questions": ["question 1", "question 2"],
  "participants": ["name1", "name2"]
}}

Respond ONLY with valid JSON, no other text."""

    response = _get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


def _generate_work_plan(available_hours: float, date: str, priorities: List[str]) -> dict:
    tasks = (
        repo.list_tasks(status="pending")
        + repo.list_tasks(status="in_progress")
        + repo.list_tasks(status="blocked")
    )

    priority_score = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    def score(task):
        s = priority_score.get(task["priority"], 1)
        if task.get("due_date") and task["due_date"] < date:
            s += 2
        if task.get("due_date") == date:
            s += 1
        if task["status"] == "blocked":
            s -= 1
        if priorities:
            tags = task.get("tags") or []
            if any(p.lower() in [t.lower() for t in tags] for p in priorities):
                s += 1
        return s

    scored = sorted(tasks, key=score, reverse=True)
    scheduled, deferred, risk_warnings = [], [], []
    hours_used = 0.0

    for task in scored:
        est_hours = 2.0 if task["priority"] == "critical" else 1.0

        if task["status"] == "blocked":
            risk_warnings.append(f"Task #{task['id']} '{task['title']}' is BLOCKED")
            deferred.append(task)
            continue

        if task.get("due_date") and task["due_date"] < date:
            risk_warnings.append(f"Task #{task['id']} '{task['title']}' is OVERDUE (due {task['due_date']})")

        if hours_used + est_hours <= available_hours:
            scheduled.append({**task, "estimated_hours": est_hours})
            hours_used += est_hours
        else:
            deferred.append(task)

    return {
        "date": date,
        "available_hours": available_hours,
        "hours_scheduled": hours_used,
        "scheduled_tasks": scheduled,
        "deferred_tasks": deferred,
        "recommended_focus": [t["title"] for t in scheduled[:3]],
        "risk_warnings": risk_warnings,
        "summary": (
            f"Plan for {date}: {len(scheduled)} tasks scheduled "
            f"({hours_used:.1f}h), {len(deferred)} deferred."
        ),
    }


def _generate_weekly_report() -> dict:
    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    all_tasks = repo.list_tasks(limit=200)

    completed = [t for t in all_tasks if t["status"] == "completed"]
    overdue = [
        t for t in all_tasks
        if t["status"] not in ("completed", "cancelled")
        and t.get("due_date") and t["due_date"] < str(today)
    ]
    blocked = [t for t in all_tasks if t["status"] == "blocked"]
    pending = [t for t in all_tasks if t["status"] == "pending"]
    in_progress = [t for t in all_tasks if t["status"] == "in_progress"]

    next_week_focus = sorted(
        [t for t in pending + in_progress if t["priority"] in ("high", "critical")],
        key=lambda t: ({"critical": 0, "high": 1}.get(t["priority"], 2)),
    )[:5]

    return {
        "week_start": str(week_start),
        "report_date": str(today),
        "statistics": {
            "total_tasks": len(all_tasks),
            "completed": len(completed),
            "in_progress": len(in_progress),
            "pending": len(pending),
            "blocked": len(blocked),
            "overdue": len(overdue),
        },
        "completed_tasks": completed[:10],
        "overdue_tasks": overdue,
        "blocked_tasks": blocked,
        "next_week_priorities": next_week_focus,
        "summary": (
            f"This week: {len(completed)} completed, {len(overdue)} overdue, "
            f"{len(blocked)} blocked. {len(pending)} tasks pending."
        ),
    }


def execute_planning_tool(name: str, tool_input: dict) -> dict:
    if name == "extract_meeting_actions":
        inp = ExtractMeetingInput(**tool_input)
        try:
            result = _extract_with_llm(inp.meeting_notes, inp.meeting_title)
            return {"success": True, "extraction": result}
        except Exception as e:
            return {"success": False, "error": f"Extraction failed: {e}"}

    if name == "generate_work_plan":
        inp = GenerateWorkPlanInput(**tool_input)
        date = inp.date or str(datetime.utcnow().date())
        plan = _generate_work_plan(inp.available_hours, date, inp.priorities or [])
        return {"success": True, "plan": plan}

    if name == "generate_weekly_report":
        report = _generate_weekly_report()
        return {"success": True, "report": report}

    return {"success": False, "error": f"Unknown planning tool: {name}"}
