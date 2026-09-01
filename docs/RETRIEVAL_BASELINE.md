# Retrieval baseline

Date: 2026-09-01  
Encoders: `BAAI/bge-small-en-v1.5` + `clip-ViT-B-32` (`EVAL_REAL_ENCODERS=true`)  
Set: `qa_500_hard.json` (500 ID-free questions: 200 text / 175 table / 125 figure)  
Script: `python scripts/evaluation/run_hard_eval.py`

## Hard 500

Gold is plant + page. Identifier ILIKE is off. Questions do not contain `SKU-` or `FIG-` tokens.

Pixel-only questions (image tables, figures) count as a hit for the text-only system only if the answer string is present in extractable PDF text.

| System | Recall@10 | text | table | figure |
|---|---|---|---|---|
| Text-only hybrid (BM25 + BGE) | **0.55** | 1.00 | 0.429 | 0.00 |
| + page/crop CLIP splice | **0.872** | 1.00 | 0.634 | 1.00 |

Plant PDFs under `fixtures/hard/` are generated and gitignored. Rebuild them before running the eval.

```
cd backend
python scripts/evaluation/build_hard_set.py
python scripts/evaluation/run_hard_eval.py
```

## Small fixture (acme policy)

Set: `fixtures/acme_refund_policy.pdf` + `qa_ground_truth.json` (3 questions), Recall@5, `MOCK_LLM_AND_EMBEDDINGS=true`

| Selective embedding | Chunks stored | Recall@5 | MRR | P@5 |
|---|---|---|---|---|
| on (default) | 1 | 1.00 | 1.000 | 0.20 |
| off | 1 | 1.00 | 1.000 | 0.20 |

**Decision: keep `ENABLE_SELECTIVE_EMBEDDING=true`.**
