"""
Parse PDFs and export chunks to JSONL for offline embedding.
This simulates a split pipeline: parse in one stage, embed later.
"""

import asyncio
import json
from pathlib import Path

from app.services.ingestion import ingestion_service

PDFS = [
    "scripts/test_pdfs/attention_paper.pdf",
    "scripts/test_pdfs/ml_yearning.pdf",
    "scripts/test_pdfs/python_tutorial.pdf",
]

MAX_PAGES_PER_DOC = 20
OUTPUT_PATH = "scripts/evaluation/chunks_export.jsonl"


async def main():
    out_path = Path(OUTPUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with out_path.open("w", encoding="utf-8") as f:
        for pdf in PDFS:
            path = Path(pdf)
            if not path.exists():
                continue
            data = path.read_bytes()
            pages = await ingestion_service.parse_document(data, "application/pdf")
            pages = pages[:MAX_PAGES_PER_DOC]
            for page in pages:
                chunks = ingestion_service.chunk_text(page["content"], page["page_number"])
                for chunk in chunks:
                    f.write(json.dumps(chunk) + "\n")
                    count += 1

    print(f"Exported {count} chunks to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
