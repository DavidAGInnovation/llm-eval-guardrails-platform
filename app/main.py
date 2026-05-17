import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import datasets, health, policies, runs
from app.core.config import get_settings
from app.core.logging import configure_logging, set_request_id
from app.core.telemetry import setup_tracing
from app.db.base import Base
from app.db.session import engine

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()

app = FastAPI(title="LLM Evaluation & Guardrails Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

setup_tracing(app)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.on_event("startup")
def startup_event() -> None:
    # For local startup convenience; production should rely on migrations.
    Base.metadata.create_all(bind=engine)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = set_request_id(request.headers.get("x-request-id"))
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_error", path=request.url.path)
        return JSONResponse(status_code=500, content={"error": "internal_error", "request_id": rid})
    response.headers["x-request-id"] = rid
    return response


app.include_router(health.router)
app.include_router(datasets.router)
app.include_router(policies.router)
app.include_router(runs.router)
