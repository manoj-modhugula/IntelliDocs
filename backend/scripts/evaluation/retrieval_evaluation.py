"""
Retrieval Evaluation with Recall@K Metrics
==========================================
This script measures retrieval quality using standard IR metrics.

Metrics:
- Recall@K: Did the correct chunk appear in top K results?
- MRR (Mean Reciprocal Rank): Average of 1/rank for correct results
- Precision@K: What fraction of retrieved results are relevant?

Offline retrieval metrics (no LLM calls).
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.retrieval import RetrievalService
from app.services.embedding import EmbeddingService
from app.core.database import async_session
from app.core.config import settings


@dataclass
class RetrievalTestCase:
    """A test case for retrieval evaluation."""
    question: str
    relevant_keywords: List[str]  # Keywords that MUST appear in correct chunk
    category: str  # e.g., "transformer", "python", "ml"


_EVAL_DIR = Path(__file__).resolve().parent
_GROUND_TRUTH_PATH = _EVAL_DIR / "qa_ground_truth.json"


_QA500_PATH = _EVAL_DIR / "qa_500.json"


def load_test_cases(path: Optional[Path] = None) -> List["RetrievalTestCase"]:
    """Prefer the checked-in labeled set; fall back to the built-in paper questions."""
    if path is None:
        env_path = os.environ.get("RETRIEVAL_EVAL_SET")
        if env_path:
            path = Path(env_path)
        elif _QA500_PATH.exists() and os.environ.get("USE_QA500") == "1":
            path = _QA500_PATH
    target = path or _GROUND_TRUTH_PATH
    if target.exists():
        data = json.loads(target.read_text())
        return [
            RetrievalTestCase(
                question=case["question"],
                relevant_keywords=list(case["relevant_keywords"]),
                category=case.get("category", "general"),
            )
            for case in data.get("cases", [])
        ]
    return PAPER_TEST_CASES


# Harder test cases to stress keyword/structured retrieval (used if no JSON)
PAPER_TEST_CASES = [
    # Attention Is All You Need paper (first 12 pages)
    RetrievalTestCase(
        question="What BLEU score did the Transformer achieve on WMT 2014 English-German?",
        relevant_keywords=["BLEU", "41.8"],
        category="transformer"
    ),
    RetrievalTestCase(
        question="Where is the paper published and in which year?",
        relevant_keywords=["NIPS", "2017"],
        category="transformer"
    ),
    RetrievalTestCase(
        question="What does the Transformer dispense with entirely?",
        relevant_keywords=["recurrence", "convolutions"],
        category="transformer"
    ),
    RetrievalTestCase(
        question="What is WMT 2014 English-German?",
        relevant_keywords=["WMT", "English", "German"],
        category="transformer"
    ),

    # ML Yearning (first 20 pages)
    RetrievalTestCase(
        question="What are dev and test sets?",
        relevant_keywords=["dev set", "test set"],
        category="ml"
    ),
    RetrievalTestCase(
        question="Explain mismatched dev and test sets.",
        relevant_keywords=["mismatched", "dev", "test"],
        category="ml"
    ),
    RetrievalTestCase(
        question="What is avoidable bias?",
        relevant_keywords=["avoidable", "bias"],
        category="ml"
    ),
    RetrievalTestCase(
        question="What is human-level performance used for?",
        relevant_keywords=["human-level", "performance"],
        category="ml"
    ),
    RetrievalTestCase(
        question="What is a dev set?",
        relevant_keywords=["dev", "set"],
        category="ml"
    ),
    RetrievalTestCase(
        question="What is a test set?",
        relevant_keywords=["test", "set"],
        category="ml"
    ),
]


def chunk_contains_keywords(
    chunk_content: str,
    keywords: List[str],
    min_keywords: int = 2
) -> Tuple[bool, int]:
    """
    Check if chunk contains any of the required keywords.
    Returns (is_relevant, num_keywords_found)
    """
    content_lower = chunk_content.lower()
    found = sum(1 for kw in keywords if kw.lower() in content_lower)
    return found >= min_keywords, found


async def evaluate_retrieval(
    workspace_id: str = "eval-workspace",
    top_k: int = 5,
    use_naive: bool = False,
    cases: Optional[List[RetrievalTestCase]] = None,
) -> Dict:
    """
    Evaluate retrieval quality using Recall@K and MRR.
    
    Args:
        workspace_id: The workspace containing test documents
        top_k: Number of results to retrieve
        use_naive: If True, use simple semantic search; else use advanced
    
    Returns:
        Dictionary with evaluation metrics
    """
    retrieval = RetrievalService()
    test_cases = cases if cases is not None else load_test_cases()
    
    results = {
        "mode": "naive" if use_naive else "advanced",
        "top_k": top_k,
        "test_cases": len(test_cases),
        "recall_at_k": 0.0,
        "mrr": 0.0,
        "precision_at_k": 0.0,
        "per_case_results": []
    }
    
    total_recall = 0
    total_mrr = 0.0
    total_precision = 0.0
    
    async with async_session() as db:
        for test_case in test_cases:
            print(f"\nQ: {test_case.question}")
            
            # Retrieve chunks
            try:
                if use_naive:
                    # Naive: simple semantic search only
                    settings.ENABLE_MULTI_GRANULARITY = False
                    chunks = await retrieval.search(
                        db=db,
                        query=test_case.question,
                        top_k=top_k,
                        workspace_id=workspace_id,
                        use_multi_granularity=False,
                        strategy="SEMANTIC"
                    )
                else:
                    # Advanced: multi-granularity + hybrid
                    settings.ENABLE_MULTI_GRANULARITY = True
                    chunks = await retrieval.search(
                        db=db,
                        query=test_case.question,
                        top_k=top_k,
                        workspace_id=workspace_id,
                        use_multi_granularity=True,
                        strategy="HYBRID"
                    )
            except Exception as e:
                print(f"  ERROR: {e}")
                results["per_case_results"].append({
                    "question": test_case.question,
                    "error": str(e)
                })
                continue
            
            # Evaluate results
            found_relevant = False
            first_relevant_rank = None
            relevant_count = 0
            
            for rank, (chunk, score) in enumerate(chunks, 1):
                is_relevant, kw_count = chunk_contains_keywords(
                    chunk.content, 
                    test_case.relevant_keywords
                )
                
                if is_relevant:
                    relevant_count += 1
                    if first_relevant_rank is None:
                        first_relevant_rank = rank
                        found_relevant = True
            
            # Calculate metrics for this case
            recall = 1 if found_relevant else 0
            mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
            precision = relevant_count / top_k if top_k > 0 else 0.0
            
            total_recall += recall
            total_mrr += mrr
            total_precision += precision
            
            status = "✓" if found_relevant else "✗"
            print(f"  {status} Recall: {recall}, MRR: {mrr:.3f}, P@{top_k}: {precision:.2f}")
            print(f"    Retrieved {len(chunks)} chunks, {relevant_count} relevant")
            
            results["per_case_results"].append({
                "question": test_case.question,
                "category": test_case.category,
                "recall": recall,
                "mrr": mrr,
                "precision": precision,
                "chunks_retrieved": len(chunks),
                "relevant_found": relevant_count
            })
    
    # Aggregate metrics
    n = len(test_cases)
    results["recall_at_k"] = total_recall / n if n > 0 else 0
    results["mrr"] = total_mrr / n if n > 0 else 0
    results["precision_at_k"] = total_precision / n if n > 0 else 0
    
    return results


async def main():
    print("=" * 70)
    print("RETRIEVAL EVALUATION - Recall@5, MRR, Precision@5")
    print("=" * 70)
    cases = load_test_cases()
    print(f"Test cases: {len(cases)}")
    print(f"Source: { _GROUND_TRUTH_PATH if _GROUND_TRUTH_PATH.exists() else 'built-in paper questions' }")
    
    # Evaluate naive mode
    print("\n" + "=" * 70)
    print("1. NAIVE RETRIEVAL (simple semantic search)")
    print("=" * 70)
    naive_results = await evaluate_retrieval(use_naive=True, top_k=5)
    
    # Evaluate advanced mode
    print("\n" + "=" * 70)
    print("2. ADVANCED RETRIEVAL (multi-granularity + hybrid)")
    print("=" * 70)
    advanced_results = await evaluate_retrieval(use_naive=False, top_k=5)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY - Retrieval Quality Metrics")
    print("=" * 70)
    print(f"""
┌─────────────────────────────────────────────────────────────┐
│ Metric              │ Naive          │ Advanced       │ Δ   │
├─────────────────────────────────────────────────────────────┤
│ Recall@5            │ {naive_results['recall_at_k']*100:5.1f}%         │ {advanced_results['recall_at_k']*100:5.1f}%         │ {(advanced_results['recall_at_k']-naive_results['recall_at_k'])*100:+.1f}%│
│ MRR                 │ {naive_results['mrr']:.3f}          │ {advanced_results['mrr']:.3f}          │ {advanced_results['mrr']-naive_results['mrr']:+.3f}│
│ Precision@5         │ {naive_results['precision_at_k']*100:5.1f}%         │ {advanced_results['precision_at_k']*100:5.1f}%         │ {(advanced_results['precision_at_k']-naive_results['precision_at_k'])*100:+.1f}%│
└─────────────────────────────────────────────────────────────┘
""")
    
    print(
        f"Naive Recall@5 {naive_results['recall_at_k']*100:.0f}% -> "
        f"advanced {advanced_results['recall_at_k']*100:.0f}%"
    )
    
    # Save results
    output = {
        "naive": naive_results,
        "advanced": advanced_results,
        "improvement": {
            "recall_delta": improvement,
            "mrr_delta": advanced_results['mrr'] - naive_results['mrr'],
            "precision_delta": advanced_results['precision_at_k'] - naive_results['precision_at_k']
        }
    }
    
    output_path = os.path.join(os.path.dirname(__file__), "retrieval_metrics.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
