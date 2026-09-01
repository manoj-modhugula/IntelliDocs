#!/usr/bin/env python3
"""
Seed the database with IntelliDocs technical documentation.
Run this before measure_accuracy.py to ensure test queries have relevant content.
Usage: python scripts/seed_intellidocs_knowledge.py
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# IntelliDocs documentation content for RAG retrieval
INTELLIDOCS_KNOWLEDGE = """
# IntelliDocs Technical Documentation

## Overview
IntelliDocs is an AI-powered document intelligence platform that enables users to upload documents and ask questions using natural language. The system uses RAG (Retrieval-Augmented Generation) to provide accurate, cited answers.

## Architecture
- **Backend**: Python FastAPI with async support
- **Frontend**: Next.js 14 with Tailwind CSS
- **Database**: PostgreSQL with pgvector extension for vector search
- **Embeddings**: Amazon Titan Embeddings via AWS Bedrock
- **LLM**: Amazon Nova Pro or Claude via AWS Bedrock
- **Cache**: Redis (Upstash) for semantic caching
- **Storage**: AWS S3 for document storage

## Search System
The hybrid search combines:
1. **Semantic search**: pgvector cosine similarity with Titan embeddings
2. **Keyword search**: PostgreSQL full-text search (BM25-style with ts_rank)
3. **Reciprocal Rank Fusion (RRF)**: Merges results from both methods
4. **Agentic query routing**: LLM selects optimal strategy (SEMANTIC, KEYWORD, or HYBRID)

## File Formats
Supported formats: PDF, DOCX, TXT, Markdown (.md)

## Streaming
Responses use Server-Sent Events (SSE) for real-time token streaming. Time-to-first-token is optimized with Redis semantic caching for repeated queries.

## Deployment
- **Lambda**: S3-triggered ingestion (chunking, embeddings, pgvector)
- **Terraform**: IaC for ECS, S3, CloudWatch
- **Vercel**: Frontend hosting
- **Docker**: Containerized backend

## pgvector and Vector Search
pgvector is a PostgreSQL extension for vector similarity search. IntelliDocs uses pgvector for storing Titan embeddings and performing cosine similarity search. The vector dimension matches Amazon Titan Embeddings output.

## BM25 and Full-Text Search
PostgreSQL full-text search uses ts_rank for BM25-style ranking. Keyword search complements semantic search for exact term matching (e.g. product names, version numbers).

## Upstash Redis
Upstash provides serverless Redis for semantic caching. Cache keys use exact hash match and cosine similarity for semantic hits.
"""


SEED_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
SEED_DOCUMENT_ID = "00000000-0000-0000-0000-000000000002"


async def seed_knowledge():
    """Insert IntelliDocs documentation as chunks."""
    from sqlalchemy import text
    from app.core.database import async_session
    from app.services.embedding import embedding_service
    from app.core.utils import utc_now_naive

    doc_id = SEED_DOCUMENT_ID
    workspace_id = SEED_WORKSPACE_ID
    now = utc_now_naive()

    # Split into chunks (simple split by double newline)
    paragraphs = [p.strip() for p in INTELLIDOCS_KNOWLEDGE.split("\n\n") if p.strip()]
    chunks_text = []
    current = []
    current_len = 0
    for p in paragraphs:
        if current_len + len(p) > 400 and current:
            chunks_text.append("\n\n".join(current))
            current = [p]
            current_len = len(p)
        else:
            current.append(p)
            current_len += len(p)
    if current:
        chunks_text.append("\n\n".join(current))

    async with async_session() as db:
        # Ensure workspace exists
        await db.execute(text("""
            INSERT INTO workspaces (id, name, description, created_at, updated_at)
            VALUES (:id, 'IntelliDocs Knowledge', 'Seeded documentation', :now, :now)
            ON CONFLICT (id) DO NOTHING
        """), {"id": workspace_id, "now": now})

        # Delete existing seed chunks to avoid duplicates
        await db.execute(text("DELETE FROM chunks WHERE document_id = :doc_id"), {"doc_id": doc_id})

        # Create document (upsert)
        await db.execute(text("""
            INSERT INTO documents (id, name, file_type, file_size, s3_key, status, chunk_count, workspace_id, created_at, updated_at)
            VALUES (:id, 'intellidocs-technical-docs.md', 'md', 5000, NULL, 'ready', :count, :ws, :now, :now)
            ON CONFLICT (id) DO UPDATE SET chunk_count = :count, status = 'ready', updated_at = :now
        """), {"id": doc_id, "count": len(chunks_text), "ws": workspace_id, "now": now})

        # Get embeddings for each chunk
        for i, content in enumerate(chunks_text):
            chunk_id = str(uuid.uuid4())
            embedding = await embedding_service.embed_text(content)
            emb_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"

            await db.execute(text("""
                INSERT INTO chunks (id, document_id, content, chunk_index, embedding, token_count, created_at)
                VALUES (:id, :doc_id, :content, :idx, CAST(:emb AS vector), 100, :now)
            """), {"id": chunk_id, "doc_id": doc_id, "content": content, "idx": i, "emb": emb_str, "now": now})

        await db.commit()
        print(f"✓ Seeded {len(chunks_text)} chunks from IntelliDocs documentation")
        print(f"  Document ID: {doc_id}, Workspace: {workspace_id}")
        print("  Run measure_accuracy.py with workspaceId for best results")


if __name__ == "__main__":
    asyncio.run(seed_knowledge())
