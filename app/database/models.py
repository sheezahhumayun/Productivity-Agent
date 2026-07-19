from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import DB_PATH


class Base(DeclarativeBase):
    pass


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="pending")
    due_date = Column(String(20), nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    source = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NoteModel(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExecutionLogModel(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, index=True)
    user_request = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    tools_called = Column(JSON, nullable=False, default=list)
    step_count = Column(Integer, default=0)
    approval_status = Column(JSON, nullable=False, default=dict)
    errors = Column(JSON, nullable=False, default=list)
    final_outcome = Column(Text, nullable=True)
    status = Column(String(20), default="running")
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def get_session() -> Session:
    engine = get_engine()
    return Session(engine)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
