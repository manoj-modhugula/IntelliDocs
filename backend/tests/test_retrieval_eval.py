"""Labeled retrieval eval: keyword helper, ground truth, Recall@K on the fixture PDF."""

import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT / "scripts" / "evaluation"))

from retrieval_evaluation import (  # noqa: E402
    chunk_contains_keywords,
    evaluate_retrieval,
    load_test_cases,
)

from app.core.config import settings
from app.core.database import async_session
from app.models import Document, Workspace
from app.services.ingestion import ingestion_service

EVAL_WS = "eval-workspace"
PDF = BACKEND_ROOT / "scripts" / "evaluation" / "fixtures" / "acme_refund_policy.pdf"


def test_load_checked_in_ground_truth():
    cases = load_test_cases()
    assert len(cases) == 3
    assert any("14 days" in c.relevant_keywords for c in cases)


def test_chunk_is_relevant_when_two_keywords_match():
    ok, found = chunk_contains_keywords(
        "Customers may request a refund within 14 days after purchase.",
        ["14 days", "refund"],
    )
    assert ok is True
    assert found == 2


def test_chunk_is_irrelevant_without_keywords():
    ok, found = chunk_contains_keywords("unrelated appendix table", ["14 days", "refund"])
    assert ok is False
    assert found == 0


async def _ingest_fixture(*, selective: bool) -> int:
    settings.MOCK_LLM_AND_EMBEDDINGS = True
    settings.ENABLE_SELECTIVE_EMBEDDING = selective
    async with async_session() as db:
        ws = await db.get(Workspace, EVAL_WS)
        if not ws:
            db.add(Workspace(id=EVAL_WS, name="Eval", user_id="eval-user"))
            await db.flush()
        existing = (
            await db.execute(select(Document).where(Document.workspace_id == EVAL_WS))
        ).scalars().all()
        for doc in existing:
            await db.delete(doc)
        await db.commit()

        doc_id = str(uuid.uuid4())
        db.add(
            Document(
                id=doc_id,
                name="acme_refund_policy.pdf",
                file_type="application/pdf",
                file_size=PDF.stat().st_size,
                status="pending",
                workspace_id=EVAL_WS,
            )
        )
        await db.commit()
        return await ingestion_service.process_document(
            db, doc_id, PDF.read_bytes(), "application/pdf"
        )


@pytest.mark.asyncio
async def test_labeled_hybrid_recall_selective_on(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM_AND_EMBEDDINGS", True)
    monkeypatch.setattr(settings, "ENABLE_HYDE", False)
    monkeypatch.setattr(settings, "ENABLE_MULTI_QUERY", False)
    count = await _ingest_fixture(selective=True)
    assert count >= 1
    results = await evaluate_retrieval(workspace_id=EVAL_WS, top_k=5, use_naive=False)
    assert results["recall_at_k"] >= 0.66, results


@pytest.mark.asyncio
async def test_labeled_hybrid_recall_selective_off(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM_AND_EMBEDDINGS", True)
    monkeypatch.setattr(settings, "ENABLE_HYDE", False)
    monkeypatch.setattr(settings, "ENABLE_MULTI_QUERY", False)
    count = await _ingest_fixture(selective=False)
    assert count >= 1
    results = await evaluate_retrieval(workspace_id=EVAL_WS, top_k=5, use_naive=False)
    assert results["recall_at_k"] >= 0.66, results
