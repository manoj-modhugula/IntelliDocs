#!/usr/bin/env python3
"""
Seed RAG eval dataset from HuggingFace (rag-mini-wikipedia).
Free dataset: 918 QA pairs, 3.2k passages.

Install: pip install datasets
Run: python scripts/seed_rag_mini_wikipedia.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SEED_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
SEED_DOCUMENT_ID = "00000000-0000-0000-0000-000000000003"  # Different from IntelliDocs seed


async def seed():
    try:
        from datasets import load_dataset
    except ImportError:
        print("Install: pip install datasets")
        return

    from sqlalchemy import text
    from app.core.database import async_session
    from app.services.embedding import embedding_service
    from app.core.utils import utc_now_naive
    import uuid

    print("Loading rag-mini-wikipedia from HuggingFace...")
    try:
        ds = load_dataset("rag-datasets/rag-mini-wikipedia", "text-corpus")
        ds = ds["passages"] if "passages" in ds else ds[list(ds.keys())[0]]
    except Exception:
        ds = load_dataset("rag-datasets/rag-mini-wikipedia", split="test")

    # Get passages (corpus) - try common column names
    passages = []
    for col in ("passage", "text", "content", "context"):
        if col in ds.column_names:
            passages = [x for x in ds[col][:800] if x and len(str(x).strip()) >= 20]
            break
    if not passages and ds.column_names:
        col = ds.column_names[0]
        passages = [x for x in ds[col][:800] if x and len(str(x).strip()) >= 20]
    if not passages:
        print("No passages found. Dataset columns:", ds.column_names)
        return

    now = utc_now_naive()
    doc_id = SEED_DOCUMENT_ID
    workspace_id = SEED_WORKSPACE_ID

    async with async_session() as db:
        await db.execute(text("""
            INSERT INTO workspaces (id, name, description, created_at, updated_at)
            VALUES (:id, 'RAG Eval', 'Wikipedia QA dataset', :now, :now)
            ON CONFLICT (id) DO NOTHING
        """), {"id": workspace_id, "now": now})
        await db.execute(text("DELETE FROM chunks WHERE document_id = :doc_id"), {"doc_id": doc_id})
        await db.execute(text("""
            INSERT INTO documents (id, name, file_type, file_size, s3_key, status, chunk_count, workspace_id, created_at, updated_at)
            VALUES (:id, 'rag-mini-wikipedia.parquet', 'md', 50000, NULL, 'ready', :count, :ws, :now, :now)
            ON CONFLICT (id) DO UPDATE SET chunk_count = :count, status = 'ready', updated_at = :now
        """), {"id": doc_id, "count": len(passages), "ws": workspace_id, "now": now})

        for i, content in enumerate(passages):
            if not content or len(str(content).strip()) < 10:
                continue
            chunk_id = str(uuid.uuid4())
            embedding = await embedding_service.embed_text(str(content)[:8000])
            emb_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
            await db.execute(text("""
                INSERT INTO chunks (id, document_id, content, chunk_index, embedding, token_count, created_at)
                VALUES (:id, :doc_id, :content, :idx, CAST(:emb AS vector), 100, :now)
            """), {"id": chunk_id, "doc_id": doc_id, "content": str(content)[:10000], "idx": i, "emb": emb_str, "now": now})

        await db.commit()
        print(f"✓ Seeded {len(passages)} passages from rag-mini-wikipedia")


if __name__ == "__main__":
    asyncio.run(seed())
