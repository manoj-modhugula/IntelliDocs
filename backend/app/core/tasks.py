"""
Background task processing with Redis persistence.
Provides async task queue for document processing and other background jobs.
Falls back to in-memory queue if Redis is unavailable.
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Any, Optional
from datetime import datetime

from app.core.utils import utc_now_naive
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


@dataclass
class Task:
    """Represents a background task."""
    id: str
    name: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else utc_now_naive(),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result=data.get("result"),
            error=data.get("error"),
            progress=data.get("progress", 0.0),
            metadata=data.get("metadata", {}),
        )


class TaskQueue:
    """
    Redis-backed async task queue for background processing.
    Falls back to in-memory queue if Redis is unavailable.
    Failed tasks are moved to a dead letter queue for inspection.
    """

    QUEUE_KEY = "intellidocs:task_queue"
    TASK_PREFIX = "intellidocs:task:"
    DLQ_KEY = "intellidocs:task_dlq"
    DLQ_MAX_SIZE = 1000

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self._redis = None
        self._memory_tasks: Dict[str, Task] = {}
        self._memory_queue: deque = deque()
        self._memory_dlq: deque = deque()
        self.workers: list = []
        self.running = False
        self._lock = asyncio.Lock()
        self._use_redis = False
    
    async def _get_redis(self):
        """Get Redis client. Task queue uses in-memory; RAG cache uses Upstash REST separately."""
        if self._redis is None:
            try:
                from app.services.cache import cache_service
                # Cache uses Upstash REST API (httpx); task queue expects TCP redis client
                if hasattr(cache_service, "_redis") and getattr(cache_service, "_redis", None):
                    self._redis = cache_service._redis
                    await self._redis.ping()
                    self._use_redis = True
                    logger.info("Task queue using Redis for persistence")
                else:
                    self._use_redis = False
            except Exception:
                self._use_redis = False
        return self._redis if self._use_redis else None
    
    async def start(self):
        """Start the task queue workers."""
        if self.running:
            return
        
        self.running = True
        
        # Try to connect to Redis
        await self._get_redis()
        
        storage = "Redis" if self._use_redis else "in-memory"
        logger.info(f"Starting task queue with {self.max_workers} workers ({storage})")
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
    
    async def stop(self):
        """Stop the task queue workers."""
        self.running = False
        
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("Task queue stopped")
    
    async def _save_task(self, task: Task):
        """Save task to Redis or memory."""
        redis = await self._get_redis()
        if redis:
            try:
                await redis.set(
                    f"{self.TASK_PREFIX}{task.id}",
                    json.dumps(task.to_dict()),
                    ex=86400
                )
                return
            except Exception as e:
                logger.warning(f"Failed to save task to Redis: {e}")

        self._memory_tasks[task.id] = task

    async def _move_to_dlq(self, task: Task):
        """Move a failed task to the dead letter queue."""
        task.status = TaskStatus.DEAD_LETTER
        redis = await self._get_redis()
        if redis:
            try:
                await redis.lpush(self.DLQ_KEY, json.dumps(task.to_dict()))
                await redis.ltrim(self.DLQ_KEY, 0, self.DLQ_MAX_SIZE - 1)
                await redis.delete(f"{self.TASK_PREFIX}{task.id}")
                logger.warning(f"Task {task.id} moved to DLQ: {task.error}")
                return
            except Exception as e:
                logger.warning(f"Failed to move task {task.id} to DLQ in Redis: {e}")

        self._memory_dlq.append(task.to_dict())
        if len(self._memory_dlq) > self.DLQ_MAX_SIZE:
            self._memory_dlq.popleft()
        self._memory_tasks.pop(task.id, None)
        logger.warning(f"Task {task.id} moved to in-memory DLQ: {task.error}")
    
    async def _get_task(self, task_id: str) -> Optional[Task]:
        """Get task from Redis or memory."""
        redis = await self._get_redis()
        if redis:
            try:
                data = await redis.get(f"{self.TASK_PREFIX}{task_id}")
                if data:
                    return Task.from_dict(json.loads(data))
            except Exception as e:
                logger.warning(f"Failed to get task from Redis: {e}")
        
        return self._memory_tasks.get(task_id)
    
    async def _pop_from_queue(self) -> Optional[tuple]:
        """Pop next task from queue."""
        redis = await self._get_redis()
        if redis:
            try:
                data = await redis.lpop(self.QUEUE_KEY)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Failed to pop from Redis queue: {e}")
        
        async with self._lock:
            if self._memory_queue:
                return self._memory_queue.popleft()
        return None
    
    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks from the queue."""
        logger.debug(f"Worker {worker_id} started")
        
        # Import here to avoid circular imports
        task_handlers: Dict[str, Callable] = {}
        
        while self.running:
            try:
                # Get next task from queue
                queue_item = await self._pop_from_queue()
                
                if not queue_item:
                    await asyncio.sleep(0.5)
                    continue
                
                task_id = queue_item.get("task_id")
                func_name = queue_item.get("func_name")
                args = queue_item.get("args", [])
                kwargs = queue_item.get("kwargs", {})
                
                # Get task
                task = await self._get_task(task_id)
                if not task:
                    continue
                
                # Update status
                task.status = TaskStatus.RUNNING
                task.started_at = utc_now_naive()
                await self._save_task(task)
                
                try:
                    logger.info(f"Worker {worker_id} executing task {task_id}: {task.name}")
                    
                    # Execute the function
                    if func_name in task_handlers:
                        func = task_handlers[func_name]
                        if asyncio.iscoroutinefunction(func):
                            result = await func(*args, **kwargs)
                        else:
                            result = func(*args, **kwargs)
                    else:
                        # Dynamic import and execution
                        result = await self._execute_task(func_name, args, kwargs)
                    
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.progress = 1.0
                    logger.info(f"Task {task_id} completed successfully")
                    
                except Exception as e:
                    task.error = str(e)
                    task.status = TaskStatus.FAILED
                    logger.error(f"Task {task_id} failed: {e}")
                    await self._move_to_dlq(task)
                    task.completed_at = utc_now_naive()
                    continue

                task.completed_at = utc_now_naive()
                await self._save_task(task)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
    
    async def _execute_task(self, func_name: str, args: list, kwargs: dict) -> Any:
        """Execute a task by function name."""
        # Handle known task types
        if func_name == "process_document":
            from app.core.tasks import process_document_background
            return await process_document_background(*args, **kwargs)
        else:
            raise ValueError(f"Unknown task function: {func_name}")
    
    async def submit(
        self,
        func: Callable,
        *args,
        name: str = "unnamed",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Submit a task for background execution."""
        task_id = str(uuid.uuid4())
        
        task = Task(
            id=task_id,
            name=name,
            status=TaskStatus.PENDING,
            created_at=utc_now_naive(),
            metadata=metadata or {},
        )
        
        # Save task
        await self._save_task(task)
        
        # Add to queue
        queue_item = {
            "task_id": task_id,
            "func_name": func.__name__ if hasattr(func, "__name__") else str(func),
            "args": list(args),
            "kwargs": kwargs,
        }
        
        redis = await self._get_redis()
        if redis:
            try:
                await redis.rpush(self.QUEUE_KEY, json.dumps(queue_item))
            except Exception as e:
                logger.warning(f"Failed to add to Redis queue: {e}")
                async with self._lock:
                    self._memory_queue.append(queue_item)
        else:
            async with self._lock:
                self._memory_queue.append(queue_item)
        
        logger.info(f"Task {task_id} ({name}) submitted to queue")
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return await self._get_task(task_id)
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status as dictionary."""
        task = await self._get_task(task_id)
        if not task:
            return None
        return task.to_dict()
    
    async def list_tasks(self, status: Optional[TaskStatus] = None) -> list:
        """List all tasks, optionally filtered by status."""
        tasks = list(self._memory_tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        return [t.to_dict() for t in tasks]

    async def get_dead_letter_tasks(self) -> list:
        """Retrieve all tasks in the dead letter queue."""
        redis = await self._get_redis()
        if redis:
            try:
                items = await redis.lrange(self.DLQ_KEY, 0, -1)
                return [json.loads(item) for item in items]
            except Exception as e:
                logger.warning(f"Failed to get DLQ from Redis: {e}")

        return list(self._memory_dlq)

    async def retry_dead_letter_task(self, task_id: str) -> Optional[str]:
        """Move a task from the DLQ back to the main queue for retry."""
        redis = await self._get_redis()
        dlq_tasks = await self.get_dead_letter_tasks()
        task_data = next((t for t in dlq_tasks if t.get("id") == task_id), None)
        if not task_data:
            return None

        task_data["status"] = TaskStatus.PENDING.value
        task_data["error"] = None
        task = Task.from_dict(task_data)

        if redis:
            try:
                await redis.lrem(self.DLQ_KEY, 1, json.dumps(task_data))
                await redis.rpush(self.QUEUE_KEY, json.dumps({
                    "task_id": task.id,
                    "func_name": task.name,
                    "args": task.metadata.get("args", []),
                    "kwargs": task.metadata.get("kwargs", {}),
                }))
                await self._save_task(task)
                logger.info(f"Task {task_id} retried from DLQ")
                return task.id
            except Exception as e:
                logger.warning(f"Failed to retry DLQ task in Redis: {e}")

        for i, t in enumerate(self._memory_dlq):
            if t.get("id") == task_id:
                self._memory_dlq.pop(i)
                break
        self._memory_tasks[task.id] = task
        self._memory_queue.append({
            "task_id": task.id,
            "func_name": task.name,
            "args": task.metadata.get("args", []),
            "kwargs": task.metadata.get("kwargs", {}),
        })
        logger.info(f"Task {task_id} retried from in-memory DLQ")
        return task.id

    async def clear_dead_letter_queue(self) -> int:
        """Clear all tasks from the dead letter queue. Returns count of cleared tasks."""
        redis = await self._get_redis()
        if redis:
            try:
                count = await redis.llen(self.DLQ_KEY)
                await redis.delete(self.DLQ_KEY)
                logger.info(f"Cleared {count} tasks from Redis DLQ")
                return count
            except Exception as e:
                logger.warning(f"Failed to clear Redis DLQ: {e}")

        count = len(self._memory_dlq)
        self._memory_dlq.clear()
        logger.info(f"Cleared {count} tasks from in-memory DLQ")
        return count


# Global task queue instance
task_queue = TaskQueue(max_workers=5)


async def process_document_background(document_id: str, file_path: str) -> Dict[str, Any]:
    """Background task for document processing."""
    from app.services.ingestion import ingestion_service
    from app.core.database import async_session
    from pathlib import Path
    
    logger.info(f"Processing document {document_id} in background")
    
    async with async_session() as db:
        try:
            path = Path(file_path)
            file_bytes = path.read_bytes()
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                file_type = "application/pdf"
            elif suffix in {".docx", ".doc"}:
                file_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                file_type = "text/plain"
            
            chunk_count = await ingestion_service.process_document(
                db=db,
                document_id=document_id,
                file_bytes=file_bytes,
                file_type=file_type,
            )
            
            logger.info(f"Document {document_id} processed: {chunk_count} chunks")
            return {"document_id": document_id, "chunk_count": chunk_count}
            
        except Exception as e:
            logger.error(f"Background processing failed for {document_id}: {e}")
            raise
