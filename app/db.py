import os
import json
import logging
import uuid
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

def count_active_tasks():
    """Count the total number of active tasks across all sessions."""
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        return sum(1 for task in _MEMORY_STORE.values() if task.get("status") == "active")
    
    try:
        db = SessionLocal()
        try:
            count = db.query(TaskState).filter(TaskState.status == "active").count()
            return count
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error counting active tasks: {e}")
        return 0

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
    # Check if this is a new task (no existing active task for this session)
    existing_task = get_active_task(session_id)
    is_new_task = existing_task is None
    
    # If starting a new task, enforce 2-task limit
    if is_new_task:
        active_count = count_active_tasks()
        if active_count >= 2:
            raise ValueError("Only 2 Task Builds at a time")
    
    # Generate unique task_id if not already present
    if "task_id" not in parameters:
        task_id = str(uuid.uuid4())
        parameters["task_id"] = task_id
        logger.info(f"Generated new task_id: {task_id} for task_type: {task_type}")
    
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        _MEMORY_STORE[session_id] = {
            "task_type": task_type,
            "parameters": parameters,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        logger.info(f"Task state saved to memory for session {session_id} with task_id {parameters.get('task_id')}")
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
                logger.info(f"Updated existing task state for session {session_id} with task_id {parameters.get('task_id')}")
            else:
                task = TaskState(
                    session_id=session_id,
                    task_type=task_type,
                    parameters=json.dumps(parameters),
                    status="active"
                )
                db.add(task)
                logger.info(f"Created new task state for session {session_id} with task_id {parameters.get('task_id')}")
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
            # Preserve task_id - it should NEVER be changed once created (enforce immutability)
            existing_task_id = task["parameters"].get("task_id")
            
            # Remove task_id from new_parameters if present to prevent overwrites
            if "task_id" in new_parameters:
                logger.warning(f"Attempt to overwrite task_id in new_parameters for session {session_id}. Ignoring.")
                new_parameters = {k: v for k, v in new_parameters.items() if k != "task_id"}
            
            task["parameters"].update(new_parameters)
            
            # Always restore the original task_id
            if existing_task_id:
                task["parameters"]["task_id"] = existing_task_id
            
            task["updated_at"] = datetime.utcnow().isoformat()
            logger.info(f"Updated task parameters for session {session_id}, task_id: {task['parameters'].get('task_id')}")
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
                # Preserve task_id - it should NEVER be changed once created (enforce immutability)
                existing_task_id = params.get("task_id")
                
                # Remove task_id from new_parameters if present to prevent overwrites
                if "task_id" in new_parameters:
                    logger.warning(f"Attempt to overwrite task_id in new_parameters for session {session_id}. Ignoring.")
                    new_parameters = {k: v for k, v in new_parameters.items() if k != "task_id"}
                
                params.update(new_parameters)
                
                # Always restore the original task_id
                if existing_task_id:
                    params["task_id"] = existing_task_id
                
                task.parameters = json.dumps(params)
                task.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated task parameters for session {session_id}, task_id: {params.get('task_id')}")
                return True
            return False
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error updating task parameters: {e}")
        return False

def clear_task_state(session_id: str):
    """Mark task as completed and trigger directory cleanup."""
    task_id_to_cleanup = None
    
    if not DATABASE_ENABLED or not SessionLocal:
        # Use in-memory fallback
        task = _MEMORY_STORE.get(session_id)
        if task:
            task_id_to_cleanup = task.get("parameters", {}).get("task_id", "unknown")
            task["status"] = "completed"
            task["updated_at"] = datetime.utcnow().isoformat()
            logger.info(f"Cleared task state for session {session_id}, task_id: {task_id_to_cleanup}")
    else:
        try:
            db = SessionLocal()
            try:
                task = db.query(TaskState).filter(TaskState.session_id == session_id).first()
                if task:
                    params = json.loads(task.parameters)
                    task_id_to_cleanup = params.get("task_id", "unknown")
                    task.status = "completed"
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Cleared task state for session {session_id}, task_id: {task_id_to_cleanup}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error clearing task state: {e}")
    
    # Clean up task directories
    if task_id_to_cleanup:
        try:
            from pathlib import Path
            import shutil
            task_dir = Path("/tmp/tasks") / task_id_to_cleanup
            if task_dir.exists():
                shutil.rmtree(task_dir)
                logger.info(f"Deleted task directory: {task_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up task directory: {e}")
