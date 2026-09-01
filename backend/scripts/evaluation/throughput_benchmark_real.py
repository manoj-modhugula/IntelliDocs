"""
Real throughput benchmark with controlled Bedrock usage.
Measures parse speed and sample embedding speed, then projects pipeline throughput.
"""

import asyncio
import time
from pathlib import Path

from app.services.ingestion import ingestion_service
from app.services.embedding import embedding_service

PDFS = [
    "scripts/test_pdfs/attention_paper.pdf",
    "scripts/test_pdfs/ml_yearning.pdf",
    "scripts/test_pdfs/python_tutorial.pdf",
]

MAX_PAGES_PER_DOC = 20
SAMPLE_EMBED_CHUNKS = 20


async def main():
    total_pages = 0
    parse_time = 0.0
    all_chunks = []

    for pdf in PDFS:
        path = Path(pdf)
        if not path.exists():
            continue
        data = path.read_bytes()
        start = time.perf_counter()
        pages = await ingestion_service.parse_document(data, "application/pdf")
        elapsed = time.perf_counter() - start

        pages = pages[:MAX_PAGES_PER_DOC]
        total_pages += len(pages)
        parse_time += elapsed

        for page in pages:
            all_chunks.extend(ingestion_service.chunk_text(page["content"], page["page_number"]))

    parse_rate = total_pages / parse_time if parse_time > 0 else 0
    print(f"Parsed {total_pages} pages in {parse_time:.2f}s => {parse_rate:.1f} pages/sec")

    # Sample embedding speed to control cost
    sample = [c["content"] for c in all_chunks[:SAMPLE_EMBED_CHUNKS]]
    start = time.perf_counter()
    await embedding_service.embed_texts(sample)
    embed_time = time.perf_counter() - start
    embed_rate = len(sample) / embed_time if embed_time > 0 else 0
    print(f"Embedded {len(sample)} chunks in {embed_time:.2f}s => {embed_rate:.1f} chunks/sec")

    print("Note: full pipeline throughput depends on embedding rate and batching.")


if __name__ == "__main__":
    asyncio.run(main())
