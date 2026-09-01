# IntelliDocs

Document Q&A over your own files. Upload PDF, DOCX, TXT, or Markdown, then ask questions and receive answers with page-level citations.

The API uses hybrid retrieval (PostgreSQL full-text search plus `pgvector` dense search), reciprocal rank fusion, and a MiniLM cross-encoder reranker. Generation runs on AWS Bedrock by default (Amazon Nova + Titan embeddings). The UI is a Next.js app that streams answers over SSE.

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

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for ingest, retrieval, generation, and auth.

## License

MIT. See [LICENSE](LICENSE).
