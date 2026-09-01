"""
Read JSONL chunks and embed them in batches.
This simulates the embedding stage of a split pipeline.
"""

import asyncio
import json
import time
from pathlib import Path

from app.services.embedding import embedding_service

INPUT_PATH = "scripts/evaluation/chunks_export.jsonl"


async def main():
    path = Path(INPUT_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Missing {INPUT_PATH}. Run parse_export_chunks.py first.")

    chunks = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))

    texts = [c["content"] for c in chunks]
    start = time.perf_counter()
    _ = await embedding_service.embed_texts(texts)
    elapsed = time.perf_counter() - start

    rate = len(texts) / elapsed if elapsed > 0 else 0
    print(f"Embedded {len(texts)} chunks in {elapsed:.2f}s ({rate:.2f} chunks/sec)")


if __name__ == "__main__":
    asyncio.run(main())
