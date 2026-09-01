"""Liveness, readiness, and dependency health checks."""

import os
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.circuit_breaker import get_all_circuit_stats
from app.core.config import settings
from app.core.database import get_db, async_session
from app.core.tasks import task_queue
from app.services.cache import cache_service

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "intellidocs-api"}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    checks = {"database": False, "redis": "optional", "bedrock": "optional"}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    try:
        await cache_service.get("health:ping")
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "degraded"

    try:
        has_creds = bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY)
        checks["bedrock"] = "configured" if has_creds else "unconfigured"
        checks["bedrock_model"] = settings.BEDROCK_MODEL_ID
        checks["mock_llm_and_embeddings"] = settings.MOCK_LLM_AND_EMBEDDINGS
    except Exception:
        checks["bedrock"] = "unknown"
        checks["mock_llm_and_embeddings"] = None

    ready = checks["database"]
    return {"status": "ready" if ready else "degraded", "checks": checks}


@router.get("/deep")
@router.get("/health/deep")
async def deep_health_check():
    checks: Dict[str, Any] = {}
    overall_healthy = True

    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = {"healthy": True}
    except Exception as e:
        checks["database"] = {"healthy": False, "error": str(e)}
        overall_healthy = False

    try:
        if cache_service._use_redis:
            result = await cache_service._execute(["PING"])
            checks["redis"] = {"healthy": result == "PONG" or result is not None}
            if not checks["redis"]["healthy"]:
                overall_healthy = False
        else:
            checks["redis"] = {"healthy": True, "mode": "in_memory"}
    except Exception as e:
        checks["redis"] = {"healthy": False, "error": str(e)}
        overall_healthy = False

    try:
        circuit_stats = get_all_circuit_stats()
        checks["circuit_breakers"] = {
            "bedrock_llm": circuit_stats["bedrock_llm"]["state"],
            "bedrock_embedding": circuit_stats["bedrock_embedding"]["state"],
            "redis": circuit_stats["redis"]["state"],
        }
        for state in checks["circuit_breakers"].values():
            if state == "open":
                overall_healthy = False
    except Exception as e:
        checks["circuit_breakers"] = {"error": str(e)}

    try:
        if not settings.MOCK_LLM_AND_EMBEDDINGS:
            import boto3

            client = boto3.client(
                "bedrock",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            )
            client.list_foundation_models(maxResults=1)
        checks["bedrock"] = {"healthy": True}
    except Exception as e:
        checks["bedrock"] = {"healthy": False, "error": str(e)}
        overall_healthy = False

    try:
        dlq_size = 0
        try:
            dlq = await task_queue.get_dead_letter_tasks()
            dlq_size = len(dlq)
        except Exception:
            pass
        checks["task_queue"] = {
            "healthy": True,
            "running": task_queue.running,
            "workers": len(task_queue.workers),
            "memory_queue_depth": len(task_queue._memory_queue),
            "dead_letter_size": dlq_size,
        }
        if dlq_size > 10:
            overall_healthy = False
    except Exception as e:
        checks["task_queue"] = {"healthy": False, "error": str(e)}

    cache_stats = cache_service.get_metrics()
    checks["cache"] = {
        "memory_entries": cache_stats.get("memory_size", 0),
        "redis_available": cache_stats.get("redis_available", False),
        "exact_hits": cache_stats.get("exact_hits", 0),
        "semantic_hits": cache_stats.get("semantic_hits", 0),
        "redis_fallbacks": cache_stats.get("redis_fallbacks", 0),
    }

    return {
        "healthy": overall_healthy,
        "checks": checks,
        "uptime_seconds": time.time() - _start_time,
        "pid": os.getpid(),
        "timestamp": time.time(),
    }
