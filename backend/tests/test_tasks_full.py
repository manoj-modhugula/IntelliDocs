"""Full tests for task queue."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.core.tasks import TaskQueue, Task, TaskStatus


class TestTaskCreation:
    """Tests for Task creation."""
    
    def test_task_default_values(self):
        """Test task has correct default values."""
        task = Task(
            id="task-1",
            name="test",
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        
        assert task.started_at is None
        assert task.completed_at is None
        assert task.result is None
        assert task.error is None
        assert task.progress == 0.0
        assert task.metadata == {}
    
    def test_task_with_metadata(self):
        """Test task with metadata."""
        task = Task(
            id="task-2",
            name="process",
            status=TaskStatus.RUNNING,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            metadata={"document_id": "doc-123"},
        )
        
        assert task.metadata["document_id"] == "doc-123"
    
    def test_task_all_statuses(self):
        """Test all task statuses."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestTaskSerialization:
    """Tests for task serialization."""
    
    def test_to_dict_basic(self):
        """Test basic to_dict conversion."""
        task = Task(
            id="task-3",
            name="test-task",
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        
        data = task.to_dict()
        
        assert data["id"] == "task-3"
        assert data["name"] == "test-task"
        assert data["status"] == "pending"
    
    def test_to_dict_with_result(self):
        """Test to_dict with result."""
        task = Task(
            id="task-4",
            name="completed-task",
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            result={"chunks": 10},
        )
        
        data = task.to_dict()
        
        assert data["result"]["chunks"] == 10
    
    def test_to_dict_with_error(self):
        """Test to_dict with error."""
        task = Task(
            id="task-5",
            name="failed-task",
            status=TaskStatus.FAILED,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            error="Processing failed",
        )
        
        data = task.to_dict()
        
        assert data["error"] == "Processing failed"
    
    def test_from_dict_basic(self):
        """Test basic from_dict conversion."""
        data = {
            "id": "task-6",
            "name": "restored-task",
            "status": "pending",
            "created_at": "2026-01-30T12:00:00",
        }
        
        task = Task.from_dict(data)
        
        assert task.id == "task-6"
        assert task.name == "restored-task"
        assert task.status == TaskStatus.PENDING
    
    def test_from_dict_all_fields(self):
        """Test from_dict with all fields."""
        data = {
            "id": "task-7",
            "name": "full-task",
            "status": "completed",
            "created_at": "2026-01-30T12:00:00",
            "started_at": "2026-01-30T12:00:01",
            "completed_at": "2026-01-30T12:00:05",
            "result": {"success": True},
            "progress": 1.0,
            "metadata": {"key": "value"},
        }
        
        task = Task.from_dict(data)
        
        assert task.status == TaskStatus.COMPLETED
        assert task.result["success"] is True
        assert task.progress == 1.0


class TestTaskQueueInit:
    """Tests for TaskQueue initialization."""
    
    def test_queue_init(self):
        """Test queue initializes correctly."""
        queue = TaskQueue(max_workers=3)
        
        assert queue.max_workers == 3
        assert queue.running is False
        assert len(queue.workers) == 0
    
    def test_queue_default_workers(self):
        """Test queue default worker count."""
        queue = TaskQueue()
        
        assert queue.max_workers == 5


class TestTaskQueueOperations:
    """Tests for TaskQueue operations."""
    
    @pytest.mark.asyncio
    async def test_submit_creates_task(self):
        """Test submit creates a task."""
        queue = TaskQueue(max_workers=1)
        
        async def dummy():
            return "done"
        
        task_id = await queue.submit(dummy, name="test")
        
        assert task_id is not None
        assert len(task_id) == 36
    
    @pytest.mark.asyncio
    async def test_submit_with_metadata(self):
        """Test submit with metadata."""
        queue = TaskQueue(max_workers=1)
        
        async def dummy():
            return "done"
        
        task_id = await queue.submit(
            dummy,
            name="test-with-meta",
            metadata={"doc_id": "123"},
        )
        
        status = await queue.get_task_status(task_id)
        
        assert status["metadata"]["doc_id"] == "123"
    
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test get_task_status returns correct status."""
        queue = TaskQueue(max_workers=1)
        
        async def dummy():
            return "done"
        
        task_id = await queue.submit(dummy, name="status-test")
        status = await queue.get_task_status(task_id)
        
        assert status is not None
        assert status["id"] == task_id
        assert status["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_get_task_not_found(self):
        """Test get_task returns None for unknown task."""
        queue = TaskQueue(max_workers=1)
        
        task = await queue.get_task("non-existent-id")
        
        assert task is None


class TestTaskQueueLifecycle:
    """Tests for TaskQueue start/stop."""
    
    @pytest.mark.asyncio
    async def test_start_creates_workers(self):
        """Test start creates worker coroutines."""
        queue = TaskQueue(max_workers=2)
        
        await queue.start()
        
        assert queue.running is True
        assert len(queue.workers) == 2
        
        await queue.stop()
    
    @pytest.mark.asyncio
    async def test_stop_clears_workers(self):
        """Test stop clears workers."""
        queue = TaskQueue(max_workers=2)
        
        await queue.start()
        await queue.stop()
        
        assert queue.running is False
        assert len(queue.workers) == 0
    
    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test multiple start calls are safe."""
        queue = TaskQueue(max_workers=1)
        
        await queue.start()
        await queue.start()  # Should not create more workers
        
        assert len(queue.workers) == 1
        
        await queue.stop()
