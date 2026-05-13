import uuid

import pytest

from app.logging_config import CorrelationIdFilter, correlation_id_var
import logging


# ── Middleware: response headers ──────────────────────────────────────────────

def test_middleware_generates_correlation_id(client):
    response = client.get("/health")
    assert "x-correlation-id" in response.headers


def test_middleware_generated_id_is_valid_uuid(client):
    response = client.get("/health")
    cid = response.headers["x-correlation-id"]
    uuid.UUID(cid)


def test_middleware_propagates_incoming_id(client):
    sent = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Correlation-ID": sent})
    assert response.headers["x-correlation-id"] == sent


def test_middleware_propagates_on_error_response(client):
    sent = str(uuid.uuid4())
    # 404 — middleware must still add the header
    response = client.get("/reactions/news/nonexistent", headers={"X-Correlation-ID": sent})
    assert response.headers.get("x-correlation-id") == sent


# ── Filter: log records contain correlation_id ────────────────────────────────

def test_filter_adds_correlation_id_to_record():
    filt = CorrelationIdFilter("reactions-service")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    token = correlation_id_var.set("trace-xyz")
    try:
        filt.filter(record)
    finally:
        correlation_id_var.reset(token)

    assert record.correlation_id == "trace-xyz"
    assert record.service == "reactions-service"


def test_filter_empty_when_no_context():
    filt = CorrelationIdFilter("reactions-service")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    filt.filter(record)
    assert record.correlation_id == ""


# ── Each request gets its own isolated correlation_id ─────────────────────────

def test_two_requests_get_independent_ids(client):
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-correlation-id"] != r2.headers["x-correlation-id"]
