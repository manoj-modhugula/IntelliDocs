"""IntelliDocs FastAPI application."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db, async_session
from app.core.observability import setup_logging, metrics as obs_metrics
from app.core.request_context import setup_request_context, clear_request_context
from app.core.tasks import task_queue
from app.routers import (
    chat,
    documents,
    workspaces,
    skills,
    health,
    auth,
    prometheus,
    conversations,
    ai,
)

setup_logging(level="INFO", structured=True)
logger = logging.getLogger(__name__)

_MAX_BODY_BYTES = 10 * 1024 * 1024


def _setup_tracing(app: FastAPI) -> None:
    """Enable OpenTelemetry only when an exporter endpoint is configured."""
    endpoint = (settings.OTEL_EXPORTER_ENDPOINT or "").strip()
    if not endpoint:
        return

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    resource = Resource.create({
        "service.name": "intellidocs-api",
        "service.version": "1.0.0",
        "deployment.environment": settings.ENVIRONMENT,
    })
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry tracing enabled")
    except Exception:
        logger.warning("OpenTelemetry exporter failed to initialize; tracing disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting IntelliDocs API")
    await init_db()

    try:
        from sqlalchemy import text

        async with async_session() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("Could not warm DB pool: %s", e)

    try:
        from sqlalchemy import text

        async with async_session() as db:
            result = await db.execute(
                text(
                    "UPDATE documents SET status = 'error', "
                    "error_message = 'Processing stuck (server restarted?)' "
                    "WHERE status = 'processing' AND updated_at < NOW() - INTERVAL '5 minutes'"
                )
            )
            if result.rowcount > 0:
                await db.commit()
                logger.info("Marked %s stuck document(s) as error", result.rowcount)
    except Exception as e:
        logger.warning("Could not mark stuck documents: %s", e)

    await task_queue.start()
    yield
    await task_queue.stop()


app = FastAPI(
    title="IntelliDocs API",
    description="Document Q&A API with retrieval-augmented generation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

_setup_tracing(app)


@app.middleware("http")
async def validate_request(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_type = request.headers.get("content-type", "")
        content_length = request.headers.get("content-length")
        has_body = bool(content_length and int(content_length) > 0)

        if has_body and "multipart/form-data" not in content_type and "application/json" not in content_type:
            return JSONResponse(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                content={"detail": "Content-Type must be application/json or multipart/form-data"},
            )

        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large (max 10MB)"},
            )

    return await call_next(request)


@app.middleware("http")
async def trace_request(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()
    request.state.request_id = request_id
    setup_request_context(request_id, logger)

    try:
        response = await call_next(request)
    finally:
        clear_request_context()

    latency_ms = (time.perf_counter() - start_time) * 1000
    path = request.url.path
    obs_metrics.histogram("http_request_latency", latency_ms, {"path": path})
    obs_metrics.increment(
        "http_requests_total",
        labels={"method": request.method, "status": str(response.status_code)},
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{latency_ms:.2f}ms"
    logger.info("%s %s %s %.2fms", request.method, path, response.status_code, latency_ms)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(ai.router, prefix="/ai", tags=["AI"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
app.include_router(skills.router, prefix="/skills", tags=["Skills"])
app.include_router(prometheus.router, prefix="/prometheus", tags=["Prometheus"])
app.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])


@app.get("/")
async def root():
    return {
        "name": "IntelliDocs API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    obs_metrics.increment("http_errors_total", labels={"type": type(exc).__name__})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
