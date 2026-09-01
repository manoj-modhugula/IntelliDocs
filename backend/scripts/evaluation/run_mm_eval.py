"""Ingest generated multimodal PDFs and print Recall@10 (CLIP on vs off)."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import async_session
from app.models import Document, Workspace
from app.services.ingestion import ingestion_service
from app.services.retrieval import RetrievalService
from scripts.evaluation.retrieval_evaluation import chunk_contains_keywords, load_test_cases

WS = "eval-multimodal"
PDF_DIR = Path(__file__).parent / "fixtures" / "multimodal"
QA = Path(__file__).parent / "qa_500.json"


async def ingest() -> int:
    settings.MOCK_LLM_AND_EMBEDDINGS = True
    settings.ENABLE_HYDE = False
    settings.ENABLE_MULTI_QUERY = False
    n = 0
    async with async_session() as db:
        ws = await db.get(Workspace, WS)
        if not ws:
            db.add(Workspace(id=WS, name="Eval multimodal", user_id="eval-user"))
            await db.flush()
        existing = (await db.execute(select(Document).where(Document.workspace_id == WS))).scalars().all()
        for doc in existing:
            await db.delete(doc)
        await db.commit()
        for pdf in sorted(PDF_DIR.glob("*.pdf")):
            doc_id = str(uuid.uuid4())
            db.add(
                Document(
                    id=doc_id,
                    name=pdf.name,
                    file_type="application/pdf",
                    file_size=pdf.stat().st_size,
                    status="pending",
                    workspace_id=WS,
                    user_id="eval-user",
                )
            )
            await db.commit()
            count = await ingestion_service.process_document(db, doc_id, pdf.read_bytes(), "application/pdf")
            n += 1
            print(f"ingested {pdf.name} chunks={count}")
    return n


async def recall(clip: bool, top_k: int = 10) -> dict:
    settings.MOCK_LLM_AND_EMBEDDINGS = True
    settings.ENABLE_CLIP = clip
    settings.ENABLE_MULTI_GRANULARITY = False
    settings.ENABLE_HYDE = False
    cases = load_test_cases(QA)
    retrieval = RetrievalService()
    hits = 0
    mrr = 0.0
    by_cat = defaultdict(lambda: {"n": 0, "hits": 0})
    async with async_session() as db:
        for case in cases:
            chunks = await retrieval.search(
                db,
                case.question,
                strategy="HYBRID",
                top_k=top_k,
                workspace_id=WS,
                use_multi_granularity=False,
            )
            rank = None
            for i, (chunk, _) in enumerate(chunks, 1):
                blob = (getattr(chunk, "caption", None) or "") + " " + (chunk.content or "")
                ok, _ = chunk_contains_keywords(blob, case.relevant_keywords, min_keywords=2)
                if ok:
                    rank = i
                    break
            by_cat[case.category]["n"] += 1
            if rank:
                hits += 1
                mrr += 1.0 / rank
                by_cat[case.category]["hits"] += 1
    n = max(len(cases), 1)
    return {
        "clip": clip,
        "n": len(cases),
        "recall_at_10": round(hits / n, 3),
        "mrr": round(mrr / n, 3),
        "by_category": {
            k: {"n": v["n"], "recall_at_10": round(v["hits"] / max(v["n"], 1), 3)}
            for k, v in by_cat.items()
        },
    }


async def main():
    if not PDF_DIR.exists() or not QA.exists():
        raise SystemExit("Run generate_multimodal_corpus.py first")
    await ingest()
    on = await recall(True)
    off = await recall(False)
    report = {"clip_on": on, "clip_off": off}
    print(json.dumps(report, indent=2))
    Path(__file__).resolve().parents[3].joinpath("docs/RETRIEVAL_BASELINE.md")
    return report


if __name__ == "__main__":
    asyncio.run(main())
