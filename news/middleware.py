import logging
import uuid
from contextvars import ContextVar

from pythonjsonlogger import json as _jsonlogger

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class JsonFormatter(_jsonlogger.JsonFormatter):
    """Wrapper so Django LOGGING dict-config can pass fmt/datefmt as kwargs."""
    def __init__(self, fmt=None, datefmt=None, **kwargs):
        args = [a for a in (fmt, datefmt) if a is not None]
        super().__init__(*args, **kwargs)


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.META.get("HTTP_X_CORRELATION_ID") or str(uuid.uuid4())
        token = correlation_id_var.set(cid)
        request.correlation_id = cid
        try:
            response = self.get_response(request)
        finally:
            correlation_id_var.reset(token)
        response["X-Correlation-ID"] = cid
        return response


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get("")
        record.service = "django-monolith"
        return True
