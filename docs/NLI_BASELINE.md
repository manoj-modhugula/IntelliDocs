# NLI grounding baseline

Date: 2026-09-01  
Filter: token/number overlap when `MOCK_LLM_AND_EMBEDDINGS=true`; MiniCheck-Flan-T5-Large when `NLI_BACKEND=minicheck` and mock is off.

## Held-out (400 atomic claims)

File: `backend/scripts/evaluation/nli_heldout.json`  
Built from the hard plant corpus: supported paraphrases plus plausible errors (wrong retention days, invented certifications).

| Metric | Value |
|---|---|
| n | **400** |
| Unsupported-claim rate, filter off | **0.125** |
| Unsupported-claim rate, filter on | **0.003** |
| Claims kept after filter | 326 |

```
cd backend
python scripts/evaluation/build_nli_heldout.py
MOCK_LLM_AND_EMBEDDINGS=true python -m scripts.evaluation.nli_evaluation
```

The smaller MNLI-style file `nli_ground_truth.json` (n=40) reports mock-stand-in label accuracy **0.90**.
