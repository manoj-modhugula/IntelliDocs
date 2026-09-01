"""
QA Evaluation without LLM judges (free metrics).
Computes EM, token-F1, and keyword recall against manual ground truth.
Uses real RAG answers by default (small number of queries to control cost).
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List

from app.core.config import settings
from app.core.database import async_session
from app.services.rag import RAGService

GROUND_TRUTH_PATH = Path(__file__).parent / "qa_ground_truth.json"


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\.\-]", "", text)
    return text


def _tokenize(text: str) -> List[str]:
    return _normalize(text).split()


def exact_match(pred: str, truth: str) -> float:
    return 1.0 if _normalize(pred) == _normalize(truth) else 0.0


def f1_score(pred: str, truth: str) -> float:
    pred_tokens = _tokenize(pred)
    truth_tokens = _tokenize(truth)
    if not pred_tokens or not truth_tokens:
        return 0.0
    common = set(pred_tokens) & set(truth_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(set(pred_tokens))
    recall = len(common) / len(set(truth_tokens))
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def keyword_recall(pred: str, keywords: List[str]) -> float:
    pred_l = pred.lower()
    hits = sum(1 for k in keywords if k.lower() in pred_l)
    return hits / len(keywords) if keywords else 0.0


async def main():
    if not GROUND_TRUTH_PATH.exists():
        raise SystemExit(f"Missing ground truth file: {GROUND_TRUTH_PATH}")

    with open(GROUND_TRUTH_PATH) as f:
        data = json.load(f)

    items = data["items"]
    rag = RAGService()

    # Cost control: keep to a small, fixed set
    max_items = len(items)

    total_em = 0.0
    total_f1 = 0.0
    total_kw = 0.0

    async with async_session() as db:
        for item in items[:max_items]:
            q = item["question"]
            expected = item["expected_answer"]
            keywords = item["expected_keywords"]

            result = await rag.answer(
                db=db,
                query=q,
                workspace_id="benchmark-workspace",
                use_cache=True,
                naive_mode=False,
            )
            answer = result.get("answer", "")

            em = exact_match(answer, expected)
            f1 = f1_score(answer, expected)
            kw = keyword_recall(answer, keywords)

            total_em += em
            total_f1 += f1
            total_kw += kw

            print(f"\nQ: {q}")
            print(f"EM: {em:.0f} | F1: {f1:.2f} | Keyword recall: {kw:.2f}")
            print(f"Answer (truncated): {answer[:160]}...")

    n = len(items[:max_items])
    print("\n=== SUMMARY ===")
    print(f"EM: {total_em / n:.2f}")
    print(f"F1: {total_f1 / n:.2f}")
    print(f"Keyword Recall: {total_kw / n:.2f}")

    # Save results
    out = {
        "count": n,
        "em": total_em / n,
        "f1": total_f1 / n,
        "keyword_recall": total_kw / n,
        "note": "Manual ground truth; no LLM judge used.",
    }
    out_path = Path(__file__).parent / "qa_metrics.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved metrics to {out_path}")


if __name__ == "__main__":
    # Keep costs down by limiting calls; real LLM only.
    settings.MOCK_LLM_AND_EMBEDDINGS = False
    asyncio.run(main())
