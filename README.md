# IntelliDocs

Document Q&A over your own files. Upload PDF, DOCX, TXT, or Markdown, then ask questions and receive answers with page-level citations.

The API uses hybrid retrieval across **text, tables, and figures**: PostgreSQL full-text search (BM25-style), `pgvector` dense search (Titan), and CLIP visual search, merged with reciprocal rank fusion and a MiniLM cross-encoder reranker. Generated answers are split into atomic claims and filtered with NLI entailment against retrieved evidence. The UI is a Next.js app that streams answers over SSE. Click a citation to open the original page with the stored page-geometry highlight. Uploads keep the original file (local `backend/data/documents/` by default, max 50 MB).

## Stack

- **API:** Python 3.11, FastAPI, SQLAlchemy, Alembic
- **Store:** PostgreSQL 15+ with pgvector, Redis (Upstash REST or `redis://`)
- **UI:** Next.js 14, Zustand
- **Models:** AWS Bedrock (NVIDIA / OpenAI / Anthropic are configurable)

## Local setup

Requirements: Python 3.11+, Node.js 18+, PostgreSQL with the `pgvector` extension. Redis is optional; without it the API uses in-process memory cache.

```bash
./setup.sh
cp backend/.env.example backend/.env   # if setup did not already copy it
# Set DATABASE_URL, JWT_SECRET_KEY, and LLM credentials in backend/.env
# Local Postgres (Homebrew): createdb intellidocs
# Enable pgvector in that database: CREATE EXTENSION vector;
# Cost-free local answers: MOCK_LLM_AND_EMBEDDINGS=true
./scripts/start-all.sh
```

- UI: http://localhost:3000
- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs

Manual start:

```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Docker

```bash
docker compose up --build
```

Compose runs PostgreSQL with pgvector, Redis, the API, and the UI. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `JWT_SECRET_KEY` in the environment (or a root `.env` that Compose loads).

## Tests

```bash
cd backend
source venv/bin/activate
pytest --cov=app -q
```

Frontend: `cd frontend && npx tsc --noEmit && npm run lint`

Labeled retrieval eval (Recall@K / MRR): `cd backend && MOCK_LLM_AND_EMBEDDINGS=true python -m pytest tests/test_retrieval_eval.py -q`. Baseline: [docs/RETRIEVAL_BASELINE.md](docs/RETRIEVAL_BASELINE.md).

500-query multimodal Recall@10 (BGE + CLIP, ID-free hard set): `cd backend && python scripts/evaluation/run_hard_eval.py` — [docs/RETRIEVAL_BASELINE.md](docs/RETRIEVAL_BASELINE.md).

NLI held-out unsupported-claim rate: `cd backend && python scripts/evaluation/build_nli_heldout.py && MOCK_LLM_AND_EMBEDDINGS=true python -m scripts.evaluation.nli_evaluation` — [docs/NLI_BASELINE.md](docs/NLI_BASELINE.md).

Playwright (API on :8000, UI on :3000): `cd frontend && npm test -- e2e/golden-path.spec.ts`

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for ingest, retrieval, generation, and auth.

## License

MIT. See [LICENSE](LICENSE).
