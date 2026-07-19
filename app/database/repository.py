from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from typing import Optional, List
from sqlalchemy import or_, and_

from app.database.models import TaskModel, NoteModel, ExecutionLogModel, get_session, init_db


def _fmt_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _task_to_dict(t: TaskModel) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "priority": t.priority,
        "status": t.status,
        "due_date": t.due_date,
        "tags": t.tags or [],
        "source": t.source,
        "notes": t.notes,
        "created_at": _fmt_dt(t.created_at),
        "updated_at": _fmt_dt(t.updated_at),
    }


def _note_to_dict(n: NoteModel) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "category": n.category,
        "tags": n.tags or [],
        "created_at": _fmt_dt(n.created_at),
        "updated_at": _fmt_dt(n.updated_at),
    }


# ── Tasks ──────────────────────────────────────────────────────────────────────

def create_task(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[str] = None,
    tags: Optional[List[str]] = None,
    source: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    init_db()
    with get_session() as session:
        task = TaskModel(
            title=title,
            description=description,
            priority=priority,
            status="pending",
            due_date=due_date,
            tags=tags or [],
            source=source,
            notes=notes,
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return _task_to_dict(task)


def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_before: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    init_db()
    with get_session() as session:
        q = session.query(TaskModel)
        if status:
            q = q.filter(TaskModel.status == status)
        if priority:
            q = q.filter(TaskModel.priority == priority)
        if due_before:
            q = q.filter(TaskModel.due_date <= due_before)
        tasks = q.order_by(TaskModel.created_at.desc()).limit(limit).all()
        result = [_task_to_dict(t) for t in tasks]
        if tag:
            result = [t for t in result if tag in (t["tags"] or [])]
        return result


def get_task(task_id: int) -> Optional[dict]:
    init_db()
    with get_session() as session:
        t = session.get(TaskModel, task_id)
        return _task_to_dict(t) if t else None


def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Optional[dict]:
    init_db()
    with get_session() as session:
        t = session.get(TaskModel, task_id)
        if not t:
            return None
        if title is not None:
            t.title = title
        if description is not None:
            t.description = description
        if priority is not None:
            t.priority = priority
        if due_date is not None:
            t.due_date = due_date
        if status is not None:
            t.status = status
        if tags is not None:
            t.tags = tags
        if notes is not None:
            t.notes = notes
        t.updated_at = _now()
        session.commit()
        session.refresh(t)
        return _task_to_dict(t)


def complete_task(task_id: int) -> Optional[dict]:
    return update_task(task_id, status="completed")


def delete_task(task_id: int) -> bool:
    init_db()
    with get_session() as session:
        t = session.get(TaskModel, task_id)
        if not t:
            return False
        session.delete(t)
        session.commit()
        return True


# ── Notes ──────────────────────────────────────────────────────────────────────

def save_note(
    title: str,
    content: str,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> dict:
    init_db()
    with get_session() as session:
        note = NoteModel(
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(note)
        session.commit()
        session.refresh(note)
        return _note_to_dict(note)


def search_notes(
    query: str,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> List[dict]:
    init_db()
    with get_session() as session:
        q = session.query(NoteModel)
        if query:
            q = q.filter(
                or_(
                    NoteModel.title.ilike(f"%{query}%"),
                    NoteModel.content.ilike(f"%{query}%"),
                )
            )
        if category:
            q = q.filter(NoteModel.category == category)
        if date_from:
            q = q.filter(NoteModel.created_at >= date_from)
        if date_to:
            q = q.filter(NoteModel.created_at <= date_to + " 23:59:59")
        notes = q.order_by(NoteModel.updated_at.desc()).limit(limit).all()
        return [_note_to_dict(n) for n in notes]


def list_notes(limit: int = 50) -> List[dict]:
    init_db()
    with get_session() as session:
        notes = session.query(NoteModel).order_by(NoteModel.updated_at.desc()).limit(limit).all()
        return [_note_to_dict(n) for n in notes]


# ── Execution Logs ─────────────────────────────────────────────────────────────

def create_log(run_id: str, user_request: str, model: str) -> int:
    init_db()
    with get_session() as session:
        log = ExecutionLogModel(
            run_id=run_id,
            user_request=user_request,
            model=model,
            tools_called=[],
            step_count=0,
            approval_status={},
            errors=[],
            status="running",
            start_time=_now(),
        )
        session.add(log)
        session.commit()
        return log.id


def update_log(log_id: int, **kwargs):
    init_db()
    with get_session() as session:
        log = session.get(ExecutionLogModel, log_id)
        if not log:
            return
        for k, v in kwargs.items():
            if hasattr(log, k):
                setattr(log, k, v)
        session.commit()


def get_recent_logs(limit: int = 20) -> List[dict]:
    init_db()
    with get_session() as session:
        logs = (
            session.query(ExecutionLogModel)
            .order_by(ExecutionLogModel.start_time.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": l.id,
                "run_id": l.run_id,
                "user_request": l.user_request,
                "model": l.model,
                "tools_called": l.tools_called,
                "step_count": l.step_count,
                "status": l.status,
                "final_outcome": l.final_outcome,
                "errors": l.errors,
                "start_time": _fmt_dt(l.start_time),
                "end_time": _fmt_dt(l.end_time),
                "duration_ms": l.duration_ms,
            }
            for l in logs
        ]
