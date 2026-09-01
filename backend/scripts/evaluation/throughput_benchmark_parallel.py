"""
Parallel parse-only throughput benchmark (simulated Lambda parallelism).
Runs multiple parse tasks concurrently across processes to measure
pages/sec under parallel load using real PDFs.
"""

import asyncio
import os
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import cycle
from pathlib import Path

from app.services.ingestion import ingestion_service

PDFS = [
    "scripts/test_pdfs/attention_paper.pdf",
    "scripts/test_pdfs/ml_yearning.pdf",
    "scripts/test_pdfs/python_tutorial.pdf",
]

MAX_PAGES_PER_DOC = 20
DEFAULT_WORKERS = min(8, os.cpu_count() or 4)


def _parse_worker(pdf_bytes: bytes, max_pages: int) -> int:
    async def _run() -> int:
        pages = await ingestion_service.parse_document(pdf_bytes, "application/pdf")
        return min(len(pages), max_pages)

    return asyncio.run(_run())


def main():
    workers = int(os.getenv("PARALLEL_WORKERS", str(DEFAULT_WORKERS)))
    if workers < 1:
        raise ValueError("PARALLEL_WORKERS must be >= 1")

    pdf_bytes_list = []
    for pdf in PDFS:
        path = Path(pdf)
        if not path.exists():
            continue
        pdf_bytes_list.append(path.read_bytes())

    if not pdf_bytes_list:
        raise FileNotFoundError("No PDFs found in scripts/test_pdfs/")

    # Round-robin PDFs to saturate workers
    pdf_cycle = cycle(pdf_bytes_list)
    tasks = [next(pdf_cycle) for _ in range(workers)]

    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_parse_worker, tasks, [MAX_PAGES_PER_DOC] * len(tasks)))
    elapsed = time.perf_counter() - start

    total_pages = sum(results)
    rate = total_pages / elapsed if elapsed > 0 else 0.0

    print("Parallel parse-only benchmark")
    print(f"Workers: {workers}")
    print(f"Total pages parsed: {total_pages}")
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Throughput: {rate:.1f} pages/sec")
    print("Note: parse-only; embeddings not included.")


if __name__ == "__main__":
    main()
