import logging
import uuid

import pytest

from user_content_service.logging_config import CorrelationIdFilter, correlation_id_var

# Note: httpx client-side logs are emitted in the test context (no ContextVar),
# so end-to-end caplog tests won't see server-side correlation_id.
# Use response header assertions instead.


# ── Middleware: response headers ──────────────────────────────────────────────

def test_middleware_generates_correlation_id(client):
    response = client.get("/internal/health")
    assert "x-correlation-id" in response.headers


def test_middleware_generated_id_is_valid_uuid(client):
    response = client.get("/internal/health")
    cid = response.headers["x-correlation-id"]
    uuid.UUID(cid)


def test_middleware_propagates_incoming_id(client):
    sent = str(uuid.uuid4())
    response = client.get("/internal/health", headers={"X-Correlation-ID": sent})
    assert response.headers["x-correlation-id"] == sent


def test_middleware_propagates_on_404(client):
    sent = str(uuid.uuid4())
    response = client.get("/favorites/check/https://no-such.url?user_id=1",
                          headers={"X-Correlation-ID": sent})
    assert response.headers.get("x-correlation-id") == sent


# ── Filter: log records contain correlation_id ────────────────────────────────

def test_filter_adds_correlation_id_to_record():
    filt = CorrelationIdFilter("user-content-service")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    token = correlation_id_var.set("uc-trace-001")
    try:
        filt.filter(record)
    finally:
        correlation_id_var.reset(token)

    assert record.correlation_id == "uc-trace-001"
    assert record.service == "user-content-service"


def test_filter_empty_when_no_context():
    filt = CorrelationIdFilter("user-content-service")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    filt.filter(record)
    assert record.correlation_id == ""


# ── Two concurrent requests don't bleed into each other ──────────────────────

def test_two_requests_get_independent_ids(client):
    r1 = client.get("/internal/health")
    r2 = client.get("/internal/health")
    assert r1.headers["x-correlation-id"] != r2.headers["x-correlation-id"]
