"""
GET /health — доступность Django, БД, память, зависимости (микросервисы).
"""

from __future__ import annotations

import os
import time

import requests
from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def _memory_rss_mb() -> float | None:
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return None


def _ping(url: str, timeout: float) -> dict:
    try:
        r = requests.get(url, timeout=timeout)
        ok = r.status_code < 500
        return {
            "ok": ok,
            "status_code": r.status_code,
            "latency_ms": round(r.elapsed.total_seconds() * 1000, 2),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def health_view(request):
    timeout = float(getattr(settings, "MICROSERVICE_TIMEOUT", 3.0))
    check_microservices = os.getenv("HEALTH_CHECK_MICROSERVICES", "true").lower() == "true"

    db_ok = True
    db_detail = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        db_ok = False
        db_detail = str(exc)[:200]

    dependencies: dict = {}
    if check_microservices and getattr(settings, "USE_MICROSERVICES", True):
        base_feed = settings.FEED_SERVICE_URL.rstrip("/")
        base_reactions = settings.REACTIONS_SERVICE_URL.rstrip("/")
        base_uc = settings.USER_CONTENT_SERVICE_URL.rstrip("/")
        dependencies["feed_service"] = _ping(f"{base_feed}/health", timeout)
        dependencies["reactions_service"] = _ping(f"{base_reactions}/health", timeout)
        dependencies["user_content_service"] = _ping(f"{base_uc}/internal/health", timeout)
    else:
        dependencies["microservices"] = {"skipped": True}

    deps_ok = True
    if check_microservices and getattr(settings, "USE_MICROSERVICES", True):
        deps_ok = all(
            isinstance(v, dict) and v.get("ok") for v in dependencies.values()
        )

    overall_ok = db_ok and deps_ok
    payload = {
        "status": "healthy" if overall_ok else "degraded",
        "service": "newshub-django",
        "database": {"ok": db_ok, "detail": db_detail},
        "memory": {"rss_mb": _memory_rss_mb()},
        "dependencies": dependencies,
        "timestamp": time.time(),
    }
    status = 200 if overall_ok else 503
    return JsonResponse(payload, status=status)
