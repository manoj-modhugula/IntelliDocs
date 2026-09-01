# Architecture

IntelliDocs is a retrieval-augmented generation (RAG) application. Users upload documents into workspaces, the API indexes text, and chat questions are answered from retrieved passages with citations.

```
Next.js (BFF /api/*)
        |
        v
FastAPI
        |
        +--> PostgreSQL + pgvector (documents, chunks, users, conversations)
        +--> Redis (exact and semantic query cache, optional)
        +--> AWS Bedrock (embeddings + LLM)
```

The Next.js app does not call Bedrock directly. Browser requests go to `/api/*` route handlers, which forward to FastAPI. That keeps auth headers and SSE streaming on the server.

## Ingest

1. `POST /documents/upload` stores a `Document` row (`pending`), writes the original file to local disk (or S3), and enqueues processing. `GET /documents/{id}/file` streams that original for the source viewer.
2. `app/services/ingestion.py` parses PDF/DOCX/TXT/MD (pdfplumber, then PyMuPDF, then pypdf).
3. For PDFs, `structured_extract.py` also pulls tables (markdown + bbox) and figures (PNG crop + caption + bbox).
4. Text is split into token-sized chunks. Optional pruning and selective embedding skip low-value **text** fragments; tables and figures are always kept.
5. Titan embeddings (1024 dimensions) are written onto `chunks.embedding`. CLIP ViT-B/32 (512-d) embeddings go onto `chunks.clip_embedding` for figures and table screenshots.
6. Document status becomes `ready` or `error`. Stuck `processing` rows are marked error on API startup.

Ingestion runs inside the API process via the background task queue (`app/core/tasks.py`). Redis backs the queue when available; otherwise the queue is in-memory.

## Query

1. `POST /chat/` or `POST /chat/stream` accepts a question, optional workspace, optional document IDs, and an optional slash skill (for example `/short`).
2. Prompt-injection patterns are stripped. A heuristic chooses SEMANTIC, KEYWORD, or HYBRID retrieval.
3. `app/services/retrieval.py` runs dense search (`pgvector` cosine), PostgreSQL `tsvector` ranking (BM25-style), and CLIP visual search, then merges with reciprocal rank fusion.
4. If confidence is low, `app/services/advanced_retrieval.py` may apply HyDE, multi-query expansion, and MiniLM cross-encoder rerank (caption + content).
5. The LLM generates an answer grounded in numbered context blocks. `grounding.py` splits the answer into atomic claims and drops claims not entailed by retrieved evidence (NLI cross-encoder, or token overlap in mock mode).
6. Citations include document name, page number, chunk type, passage excerpt, and PDF-user-space bbox. The Next.js viewer paints that rectangle on the original page.
7. Streaming uses SSE of the **filtered** answer. Similar questions can be served from the semantic cache.

## Auth and tenancy

- JWT access tokens (Argon2id password hashes).
- Workspaces belong to a user. Document and chat queries are scoped to the caller.
- In `ENVIRONMENT=production`, chat, upload, and `/ai/*` require a logged-in user. Local development can leave `REQUIRE_AUTH_FOR_CHAT=false`.

## Observability

- `GET /health` liveness, `GET /ready` readiness, `GET /health/deep` (also `/deep`) for dependencies.
- Prometheus text at `GET /prometheus/metrics`.
- OpenTelemetry traces are emitted only when `OTEL_EXPORTER_ENDPOINT` is set.

## Evaluation

- Retrieval (500 ID-free questions): `backend/scripts/evaluation/run_hard_eval.py` on `qa_500_hard.json`. Text-only hybrid vs CLIP splice. See `docs/RETRIEVAL_BASELINE.md`.
- Retrieval (small fixture): `backend/scripts/evaluation/retrieval_evaluation.py` plus `qa_ground_truth.json`.
- NLI (400 held-out claims): `backend/scripts/evaluation/nli_evaluation.py` plus `nli_heldout.json`. See `docs/NLI_BASELINE.md`.

## Future work

- Scanned-PDF OCR boxes
- True Okapi BM25 (today: PostgreSQL `ts_rank_cd`)
- Production S3 as the default original-file store
