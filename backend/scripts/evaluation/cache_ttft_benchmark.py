"""
Benchmark cache impact on LLM calls and TTFT (time to first token).
Uses real Bedrock; keeps query count small to control cost.
"""

import asyncio
import time
import logging
from typing import List

from app.core.database import async_session
from app.core.config import settings
from app.services.rag import rag_service
from app.services.llm import llm_service
from app.services.cache import cache_service


QUERIES: List[str] = [
    "What is the Transformer architecture?",
    "What is multi-head attention?",
    "How should you split your data for machine learning?",
    # repeats for cache impact (40% repeats = 2 of 5)
    "What is the Transformer architecture?",
    "How should you split your data for machine learning?",
]


async def measure_llm_calls(use_cache: bool) -> dict:
    llm_service.reset_metrics()
    cache_service.reset_metrics()
    cache_service.clear_memory_cache()
    await cache_service.invalidate_document_cache("all")

    async with async_session() as db:
        for q in QUERIES:
            await rag_service.answer(
                db=db,
                query=q,
                workspace_id="benchmark-workspace",
                use_cache=use_cache,
                naive_mode=False,
            )

    return {
        "llm": llm_service.get_metrics(),
        "cache": cache_service.get_metrics(),
        "query_count": len(QUERIES),
    }


async def measure_ttft(use_cache: bool, sample: int = 1) -> float:
    cache_service.clear_memory_cache()
    await cache_service.invalidate_document_cache("all")
    llm_service.reset_metrics()
    ttfts = []

    async with async_session() as db:
        for q in QUERIES[:sample]:
            start = time.perf_counter()
            first = None
            async for item in rag_service.answer_stream(
                db=db,
                query=q,
                workspace_id="benchmark-workspace",
                use_cache=use_cache,
            ):
                if item.get("type") == "content" and first is None:
                    first = time.perf_counter() - start
                    break
                if time.perf_counter() - start > 10:
                    break
            if first is not None:
                ttfts.append(first)

    return sum(ttfts) / len(ttfts) if ttfts else 0.0


async def main():
    print("Running cache benchmark (real Bedrock).")

    # Baseline: cache disabled
    baseline = await measure_llm_calls(use_cache=False)
    # Cache enabled
    cached = await measure_llm_calls(use_cache=True)

    llm_baseline = baseline["llm"]["generate_calls"]
    llm_cached = cached["llm"]["generate_calls"]
    reduction = (llm_baseline - llm_cached) / max(llm_baseline, 1)

    print(f"LLM calls (no cache): {llm_baseline}")
    print(f"LLM calls (cache on): {llm_cached}")
    print(f"LLM call reduction: {reduction:.2%}")
    print(f"Cache hits: {cached['cache']}")

    # TTFT
    ttft_no_cache = await measure_ttft(use_cache=False)
    ttft_cache = await measure_ttft(use_cache=True)
    if ttft_no_cache > 0:
        ttft_improvement = (ttft_no_cache - ttft_cache) / ttft_no_cache
    else:
        ttft_improvement = 0.0
    print(f"TTFT no cache: {ttft_no_cache:.3f}s")
    print(f"TTFT cache: {ttft_cache:.3f}s")
    print(f"TTFT improvement: {ttft_improvement:.2%}")


if __name__ == "__main__":
    settings.MOCK_LLM_AND_EMBEDDINGS = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(main())
