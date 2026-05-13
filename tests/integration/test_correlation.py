import logging
import uuid

import pytest

from news.middleware import CorrelationIdFilter, correlation_id_var


# ── Middleware: response headers ──────────────────────────────────────────────

@pytest.mark.django_db
def test_middleware_generates_correlation_id(client):
    response = client.get("/")
    assert "X-Correlation-ID" in response


@pytest.mark.django_db
def test_middleware_generated_id_is_valid_uuid(client):
    response = client.get("/")
    cid = response["X-Correlation-ID"]
    uuid.UUID(cid)  # raises ValueError if not a valid UUID


@pytest.mark.django_db
def test_middleware_propagates_incoming_id(client):
    sent = str(uuid.uuid4())
    response = client.get("/", HTTP_X_CORRELATION_ID=sent)
    assert response["X-Correlation-ID"] == sent


@pytest.mark.django_db
def test_middleware_propagates_on_404(client):
    sent = str(uuid.uuid4())
    response = client.get("/nonexistent-page/", HTTP_X_CORRELATION_ID=sent)
    assert response.get("X-Correlation-ID") == sent


@pytest.mark.django_db
def test_two_requests_get_independent_ids(client):
    r1 = client.get("/")
    r2 = client.get("/")
    assert r1["X-Correlation-ID"] != r2["X-Correlation-ID"]


# ── Filter: log records contain correlation_id ────────────────────────────────

def test_filter_adds_correlation_id_to_record():
    filt = CorrelationIdFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    token = correlation_id_var.set("django-trace-001")
    try:
        filt.filter(record)
    finally:
        correlation_id_var.reset(token)

    assert record.correlation_id == "django-trace-001"
    assert record.service == "django-monolith"


def test_filter_empty_when_no_context():
    filt = CorrelationIdFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    filt.filter(record)
    assert record.correlation_id == ""


# ── services.py: outgoing requests carry the correlation_id ──────────────────

def test_cid_headers_helper_returns_header_when_var_is_set():
    from news.services import _cid_headers

    token = correlation_id_var.set("outbound-cid")
    try:
        headers = _cid_headers()
    finally:
        correlation_id_var.reset(token)

    assert headers == {"X-Correlation-ID": "outbound-cid"}


def test_cid_headers_helper_returns_empty_when_no_context():
    from news.services import _cid_headers
    assert _cid_headers() == {}
