"""Prometheus text exposition for scraping."""

import os
import time
import gc
from fastapi import APIRouter, Response

from app.core.observability import metrics

router = APIRouter()

_start_time = time.time()


@router.get("/metrics", response_class=Response)
async def prometheus_metrics():
    app_metrics = metrics.export_prometheus()

    lines = [app_metrics]

    uptime_seconds = time.time() - _start_time
    lines.append("# TYPE python_uptime_seconds gauge")
    lines.append(f"python_uptime_seconds {uptime_seconds:.2f}")

    gc_stats = gc.get_stats()
    if gc_stats:
        collected = sum(s["collected"] for s in gc_stats)
        lines.append("# TYPE python_gc_objects_collected counter")
        lines.append(f"python_gc_objects_collected {collected}")

    rss = 0
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if os.uname().sysname == "Darwin":
            rss *= 1024
        lines.append("# TYPE process_resident_memory_bytes gauge")
        lines.append(f"process_resident_memory_bytes {rss}")
    except Exception:
        pass

    prometheus_text = "\n".join(lines)

    return Response(
        content=prometheus_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/health")
async def prometheus_health():
    """Health check for Prometheus scraper."""
    return {"status": "healthy"}
