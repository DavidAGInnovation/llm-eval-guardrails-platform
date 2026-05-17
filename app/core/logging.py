import logging
import sys
from contextvars import ContextVar

import structlog

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(request_id: str | None) -> str:
    rid = request_id or "generated-request-id"
    request_id_ctx_var.set(rid)
    return rid


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=getattr(logging, level.upper(), logging.INFO))

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
