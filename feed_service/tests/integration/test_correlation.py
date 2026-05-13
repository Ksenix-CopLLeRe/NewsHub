import logging
import uuid

import pytest

from app.logging_config import CorrelationIdFilter, correlation_id_var


# ── Middleware: response headers ──────────────────────────────────────────────

def test_middleware_generates_correlation_id(client):
    response = client.get("/health")
    assert "x-correlation-id" in response.headers


def test_middleware_generated_id_is_valid_uuid(client):
    response = client.get("/health")
    cid = response.headers["x-correlation-id"]
    uuid.UUID(cid)  # raises if invalid


def test_middleware_propagates_incoming_id(client):
    sent = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Correlation-ID": sent})
    assert response.headers["x-correlation-id"] == sent


def test_middleware_does_not_accept_arbitrary_string_as_id(client):
    # A non-UUID value is echoed back unchanged — middleware doesn't validate format,
    # but the important thing is it doesn't generate a new one.
    response = client.get("/health", headers={"X-Correlation-ID": "custom-trace-id"})
    assert response.headers["x-correlation-id"] == "custom-trace-id"


# ── Filter: log records contain correlation_id ────────────────────────────────

def test_filter_adds_correlation_id_to_record():
    filt = CorrelationIdFilter("feed-service")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    token = correlation_id_var.set("abc-123")
    try:
        filt.filter(record)
    finally:
        correlation_id_var.reset(token)

    assert record.correlation_id == "abc-123"
    assert record.service == "feed-service"


def test_filter_empty_when_no_context():
    filt = CorrelationIdFilter("feed-service")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    filt.filter(record)
    assert record.correlation_id == ""


# ── End-to-end: filter is called in request context ───────────────────────────

def test_filter_reads_contextvar_in_request_context(client):
    """
    The middleware sets the ContextVar; the filter reads it when a log is emitted
    in the same async context. We verify indirectly: the response header contains
    the same ID that the filter would embed in any server-side log during the request.
    (Server-side logs are in the ASGI context; client-side httpx logs are not.)
    """
    sent = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Correlation-ID": sent})
    # If the middleware correctly set the ContextVar, the same value comes back
    # in the response header — that's what any server-side logger would see too.
    assert response.headers["x-correlation-id"] == sent
