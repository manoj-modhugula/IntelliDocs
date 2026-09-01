"""
Ingest real PDFs into the database for evaluation with controlled cost.

- Limits pages per PDF to reduce embedding cost
- Uses real Bedrock embeddings
- Stores chunks in benchmark-workspace
"""

import asyncio
from pathlib import Path
from typing import List
import uuid

from sqlalchemy import text
from app.core.database import async_session
from app.services.ingestion import ingestion_service
from app.services.embedding import embedding_service
from app.models import Document, Chunk, Workspace


PDFS = [
    "scripts/test_pdfs/attention_paper.pdf",
    "scripts/test_pdfs/ml_yearning.pdf",
    "scripts/test_pdfs/python_tutorial.pdf",
]

MAX_PAGES_PER_DOC = 20  # cost control


async def main():
    async with async_session() as db:
        # Ensure workspace exists
        workspace_id = "benchmark-workspace"
        ws = await db.get(Workspace, workspace_id)
        if not ws:
            ws = Workspace(id=workspace_id, name="Benchmark", user_id="benchmark-user")
            db.add(ws)
            await db.commit()

        # Clear old benchmark data
        await db.execute(text("DELETE FROM chunks WHERE workspace_id = :ws"), {"ws": workspace_id})
        await db.execute(text("DELETE FROM documents WHERE workspace_id = :ws"), {"ws": workspace_id})
        await db.commit()

        for pdf_path in PDFS:
            path = Path(pdf_path)
            if not path.exists():
                print(f"Missing {pdf_path}, skipping")
                continue

            file_bytes = path.read_bytes()
            pages = await ingestion_service.parse_document(file_bytes, "application/pdf")
            if not pages:
                print(f"Failed to parse {path.name}")
                continue

            # Limit pages for cost control
            pages = pages[:MAX_PAGES_PER_DOC]
            all_chunks = []
            for page in pages:
                all_chunks.extend(ingestion_service.chunk_text(page["content"], page["page_number"]))

            if not all_chunks:
                print(f"No chunks for {path.name}")
                continue

            doc_id = str(uuid.uuid4())
            doc = Document(
                id=doc_id,
                name=path.name,
                file_type="pdf",
                file_size=len(file_bytes),
                status="ready",
                chunk_count=len(all_chunks),
                workspace_id=workspace_id,
            )
            db.add(doc)
            await db.commit()

            # Embed in batches
            batch_size = embedding_service.batch_size
            for batch_start in range(0, len(all_chunks), batch_size):
                batch = all_chunks[batch_start:batch_start + batch_size]
                embeddings = await embedding_service.embed_texts([c["content"] for c in batch])
                for chunk_data, embedding in zip(batch, embeddings):
                    db.add(
                        Chunk(
                            id=str(uuid.uuid4()),
                            document_id=doc_id,
                            content=chunk_data["content"],
                            page_number=chunk_data["page_number"],
                            chunk_index=chunk_data["chunk_index"],
                            token_count=chunk_data["token_count"],
                            embedding=embedding,
                            workspace_id=workspace_id,
                        )
                    )
                await db.commit()
                print(f"  Embedded batch {batch_start//batch_size + 1} ({len(batch)} chunks)")

            print(f"Ingested {path.name}: {len(pages)} pages, {len(all_chunks)} chunks")


if __name__ == "__main__":
    asyncio.run(main())
