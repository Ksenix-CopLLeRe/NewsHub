import logging
from contextvars import ContextVar

from pythonjsonlogger import json as jsonlogger

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIdFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get("")
        record.service = self.service_name
        return True


def setup_json_logging(service_name: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(service)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    handler.addFilter(CorrelationIdFilter(service_name))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
