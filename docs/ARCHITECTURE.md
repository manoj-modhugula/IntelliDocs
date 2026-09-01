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

1. `POST /documents/upload` stores a `Document` row (`pending`) and enqueues processing.
2. `app/services/ingestion.py` parses PDF/DOCX/TXT/MD (pdfplumber, then PyMuPDF, then pypdf).
3. Text is split into token-sized chunks. Optional pruning and selective embedding skip low-value fragments.
4. Titan embeddings (1024 dimensions) are written onto `chunks.embedding` (`pgvector`).
5. Document status becomes `ready` or `error`. Stuck `processing` rows are marked error on API startup.

Ingestion runs inside the API process via the background task queue (`app/core/tasks.py`). Redis backs the queue when available; otherwise the queue is in-memory.

## Query

1. `POST /chat/` or `POST /chat/stream` accepts a question, optional workspace, optional document IDs, and an optional slash skill (for example `/short`).
2. Prompt-injection patterns are stripped. A heuristic chooses SEMANTIC, KEYWORD, or HYBRID retrieval.
3. `app/services/retrieval.py` runs dense search (`pgvector` cosine) and PostgreSQL `tsvector` ranking, then merges with reciprocal rank fusion.
4. If confidence is low, `app/services/advanced_retrieval.py` may apply HyDE, multi-query expansion, and MiniLM cross-encoder rerank.
5. The LLM generates an answer grounded in numbered context blocks. Citations include document name, page number, and a passage excerpt.
6. Streaming uses SSE. Similar questions can be served from the semantic cache.

## Auth and tenancy

- JWT access tokens (Argon2id password hashes).
- Workspaces belong to a user. Document and chat queries are scoped to the caller.
- In `ENVIRONMENT=production`, chat, upload, and `/ai/*` require a logged-in user. Local development can leave `REQUIRE_AUTH_FOR_CHAT=false`.

## Observability

- `GET /health` liveness, `GET /ready` readiness, `GET /health/deep` (also `/deep`) for dependencies.
- Prometheus text at `GET /prometheus/metrics`.
- OpenTelemetry traces are emitted only when `OTEL_EXPORTER_ENDPOINT` is set.

## Future work

Not in this repository yet:

- Table and figure extraction with bounding boxes
- Visual embeddings (CLIP or equivalent) fused with text/BM25
- A PDF source viewer that highlights ranked evidence
- Claim-level NLI filtering of generated answers
- A labeled evaluation set with published Recall@K / unsupported-claim rates

Those belong in a later change. Do not treat them as current behavior.
