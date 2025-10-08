import os
import json
import logging
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_ENABLED = bool(DATABASE_URL)

# In-memory fallback when database is not available
_MEMORY_STORE = {}

if DATABASE_ENABLED:
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=300
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()
        logger.info("Database connection established")
    except Exception as e:
        logger.warning(f"Failed to initialize database: {e}. Task state management will be disabled.")
        DATABASE_ENABLED = False
else:
    logger.info("DATABASE_URL not set. Task state management will be disabled.")
    SessionLocal = None
    Base = None
    engine = None

if DATABASE_ENABLED and Base is not None:
    class TaskState(Base):
        __tablename__ = "task_state"
        
        session_id = Column(String(100), primary_key=True)
        task_type = Column(String(50), nullable=False)
        parameters = Column(Text, nullable=False, default="{}")
        status = Column(String(20), nullable=False, default="active")
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
else:
    TaskState = None

def init_db():
    if not DATABASE_ENABLED:
        logger.info("Database not enabled, skipping initialization")
        return
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")

def get_active_task(session_id: str):
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        task = _MEMORY_STORE.get(session_id)
        if task and task.get("status") == "active":
            return {
                "task_type": task["task_type"],
                "parameters": task["parameters"],
                "created_at": task["created_at"]
            }
        return None
    
    try:
        db = SessionLocal()
        try:
            task = db.query(TaskState).filter(
                TaskState.session_id == session_id,
                TaskState.status == "active"
            ).first()
            if task:
                return {
                    "task_type": task.task_type,
                    "parameters": json.loads(task.parameters),
                    "created_at": task.created_at.isoformat()
                }
            return None
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting active task: {e}")
        return None

def save_task_state(session_id: str, task_type: str, parameters: dict):
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        _MEMORY_STORE[session_id] = {
            "task_type": task_type,
            "parameters": parameters,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        logger.info(f"Task state saved to memory for session {session_id}")
        return
    
    try:
        db = SessionLocal()
        try:
            task = db.query(TaskState).filter(TaskState.session_id == session_id).first()
            if task:
                task.task_type = task_type
                task.parameters = json.dumps(parameters)
                task.status = "active"
                task.updated_at = datetime.utcnow()
            else:
                task = TaskState(
                    session_id=session_id,
                    task_type=task_type,
                    parameters=json.dumps(parameters),
                    status="active"
                )
                db.add(task)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error saving task state: {e}")

def update_task_parameters(session_id: str, new_parameters: dict):
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        task = _MEMORY_STORE.get(session_id)
        if task and task.get("status") == "active":
            task["parameters"].update(new_parameters)
            task["updated_at"] = datetime.utcnow().isoformat()
            return True
        return False
    
    try:
        db = SessionLocal()
        try:
            task = db.query(TaskState).filter(
                TaskState.session_id == session_id,
                TaskState.status == "active"
            ).first()
            if task:
                params = json.loads(task.parameters)
                params.update(new_parameters)
                task.parameters = json.dumps(params)
                task.updated_at = datetime.utcnow()
                db.commit()
                return True
            return False
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error updating task parameters: {e}")
        return False

def clear_task_state(session_id: str):
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        task = _MEMORY_STORE.get(session_id)
        if task:
            task["status"] = "completed"
            task["updated_at"] = datetime.utcnow().isoformat()
        return
    
    try:
        db = SessionLocal()
        try:
            task = db.query(TaskState).filter(TaskState.session_id == session_id).first()
            if task:
                task.status = "completed"
                task.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error clearing task state: {e}")
