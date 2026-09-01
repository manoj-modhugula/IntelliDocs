"""Tests for background task processing."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.core.tasks import TaskQueue, Task, TaskStatus


class TestTask:
    """Tests for Task dataclass."""
    
    def test_task_creation(self):
        """Test creating a task."""
        task = Task(
            id="task-123",
            name="test-task",
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        
        assert task.id == "task-123"
        assert task.name == "test-task"
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
    
    def test_task_to_dict(self):
        """Test task serialization to dict."""
        task = Task(
            id="task-123",
            name="test-task",
            status=TaskStatus.COMPLETED,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            progress=1.0,
            result={"key": "value"},
        )
        
        data = task.to_dict()
        
        assert data["id"] == "task-123"
        assert data["name"] == "test-task"
        assert data["status"] == "completed"
        assert data["progress"] == 1.0
        assert data["result"] == {"key": "value"}
    
    def test_task_from_dict(self):
        """Test task deserialization from dict."""
        data = {
            "id": "task-456",
            "name": "restored-task",
            "status": "running",
            "created_at": "2026-01-30T12:00:00",
            "progress": 0.5,
        }
        
        task = Task.from_dict(data)
        
        assert task.id == "task-456"
        assert task.name == "restored-task"
        assert task.status == TaskStatus.RUNNING
        assert task.progress == 0.5


class TestTaskStatus:
    """Tests for TaskStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestTaskQueue:
    """Tests for TaskQueue."""
    
    @pytest.mark.asyncio
    async def test_queue_creation(self):
        """Test creating a task queue."""
        queue = TaskQueue(max_workers=3)
        
        assert queue.max_workers == 3
        assert queue.running is False
    
    @pytest.mark.asyncio
    async def test_queue_start_stop(self):
        """Test starting and stopping the queue."""
        queue = TaskQueue(max_workers=2)
        
        await queue.start()
        assert queue.running is True
        assert len(queue.workers) == 2
        
        await queue.stop()
        assert queue.running is False
        assert len(queue.workers) == 0
    
    @pytest.mark.asyncio
    async def test_submit_task(self):
        """Test submitting a task."""
        queue = TaskQueue(max_workers=1)
        
        async def dummy_task():
            return "done"
        
        task_id = await queue.submit(dummy_task, name="test-task")
        
        assert task_id is not None
        assert len(task_id) == 36  # UUID
    
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """Test getting task status."""
        queue = TaskQueue(max_workers=1)
        
        async def dummy_task():
            return "done"
        
        task_id = await queue.submit(dummy_task, name="test-task")
        status = await queue.get_task_status(task_id)
        
        assert status is not None
        assert status["id"] == task_id
        assert status["name"] == "test-task"
        assert status["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_task_with_metadata(self):
        """Test submitting a task with metadata."""
        queue = TaskQueue(max_workers=1)
        
        async def dummy_task():
            return "done"
        
        task_id = await queue.submit(
            dummy_task,
            name="test-task",
            metadata={"document_id": "doc-123"}
        )
        
        status = await queue.get_task_status(task_id)
        
        assert status["metadata"]["document_id"] == "doc-123"
