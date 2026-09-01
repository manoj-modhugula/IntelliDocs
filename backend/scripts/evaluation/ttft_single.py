"""
Measure TTFT (time to first token) for a single query.
Runs once without cache, then with cache.
"""

import asyncio
import time

from app.core.config import settings
from app.core.database import async_session
from app.services.rag import rag_service
from app.services.cache import cache_service


QUERY = "What is the Transformer architecture?"


async def ttft(use_cache: bool) -> float:
    cache_service.clear_memory_cache()
    await cache_service.invalidate_document_cache("all")
    async with async_session() as db:
        start = time.perf_counter()
        async for item in rag_service.answer_stream(
            db=db,
            query=QUERY,
            workspace_id="benchmark-workspace",
            use_cache=use_cache,
        ):
            if item.get("type") == "content":
                return time.perf_counter() - start
            if time.perf_counter() - start > 15:
                break
    return 0.0


async def main():
    settings.MOCK_LLM_AND_EMBEDDINGS = False
    no_cache = await ttft(use_cache=False)
    with_cache = await ttft(use_cache=True)
    print(f"TTFT no cache: {no_cache:.3f}s")
    print(f"TTFT cache: {with_cache:.3f}s")
    if no_cache > 0:
        improvement = (no_cache - with_cache) / no_cache
    else:
        improvement = 0.0
    print(f"TTFT improvement: {improvement:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
