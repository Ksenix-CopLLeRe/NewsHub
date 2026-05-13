# JSON-логи и Correlation ID

## Проблема, которую это решает

Представь: пользователь нажал «добавить в избранное» — запрос прошёл через 3 сервиса и где-то упал.
Без этой системы ты видишь в логах:

```
INFO     Starting RSS parsing...
ERROR    Connection refused
INFO     HTTP Request: GET /feed 200
WARNING  Reaction not found
```

Это четыре строки из четырёх разных сервисов. Непонятно, какие из них относятся к одному запросу, что случилось первым, где именно упало.

С JSON-логами и Correlation ID картина меняется:

```json
{"timestamp": "2026-05-13T12:00:01Z", "level": "INFO",  "service": "django-monolith",    "correlation_id": "a1b2-...", "message": "toggle_favorite called"}
{"timestamp": "2026-05-13T12:00:01Z", "level": "INFO",  "service": "user-content-service","correlation_id": "a1b2-...", "message": "favorite added for user 42"}
{"timestamp": "2026-05-13T12:00:02Z", "level": "ERROR", "service": "reactions-service",   "correlation_id": "a1b2-...", "message": "DB connection refused"}
```

Один `grep 'a1b2-'` — и вся цепочка перед тобой в хронологическом порядке.

---

## Часть 1: JSON-логи

### Зачем JSON, а не обычный текст?

Текстовые логи читает человек. JSON-логи читает и человек, и машина.

| Текст | JSON |
|---|---|
| Ищешь руками через `grep` | Можно фильтровать по любому полю: `level`, `service`, `correlation_id` |
| Нет структуры — нет автоматики | Grafana Loki, Elasticsearch, Datadog парсят без настройки |
| Сложно добавить контекст | Каждое поле — отдельный ключ |

### Как устроено в проекте

Библиотека: `python-json-logger>=2.0.7` (добавлена в [`requirements.txt`](../requirements.txt) всех сервисов).

**FastAPI-сервисы** используют общий модуль `logging_config.py`:

```python
# feed_service/app/logging_config.py

from pythonjsonlogger import json as jsonlogger

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
```

Каждый сервис вызывает её один раз при старте:

```python
# feed_service/app/main.py
setup_json_logging("feed-service")
logger = logging.getLogger(__name__)
```

После этого любой `logger.info("что угодно")` в коде выдаёт JSON автоматически — ничего менять в остальном коде не нужно.

**Django** настраивается через стандартный `LOGGING` словарь в [`config/settings.py`](../config/settings.py):

```python
LOGGING = {
    'formatters': {
        'json': {
            '()': 'news.middleware.JsonFormatter',   # наш враппер над pythonjsonlogger
            'fmt': '%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(service)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['correlation_id'],
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
```

Почему `news.middleware.JsonFormatter`, а не `pythonjsonlogger.json.JsonFormatter` напрямую?
`pythonjsonlogger` принимает формат как позиционный аргумент, а Django LOGGING передаёт kwargs — тонкий враппер решает это несоответствие:

```python
# news/middleware.py

class JsonFormatter(_jsonlogger.JsonFormatter):
    def __init__(self, fmt=None, datefmt=None, **kwargs):
        args = [a for a in (fmt, datefmt) if a is not None]
        super().__init__(*args, **kwargs)
```

---

## Часть 2: Correlation ID

### Что это такое

Correlation ID — уникальный UUID, который живёт от начала HTTP-запроса до его конца и переходит между сервисами через заголовок `X-Correlation-ID`.

```
Browser → Django (генерирует a1b2-...) ──── X-Correlation-ID: a1b2-... ────► feed-service
                                       ──── X-Correlation-ID: a1b2-... ────► reactions-service
                                       ──── X-Correlation-ID: a1b2-... ────► user-content-service
```

Все четыре сервиса пишут этот ID в каждую строку лога. Один запрос — одна нить, по которой можно пройти через всю систему.

### Как хранится ID внутри сервиса: ContextVar

Наивное решение — передавать `correlation_id` параметром в каждую функцию. Это загрязняет сигнатуры.

Правильное решение — `contextvars.ContextVar`: переменная, видимая в текущем контексте выполнения (запросе / корутине), но изолированная от других запросов.

```python
# feed_service/app/logging_config.py

from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
```

Это работает одинаково для:
- **async FastAPI** — каждая корутина изолирована
- **sync Django (WSGI)** — каждый поток изолирован

### Middleware: откуда берётся ID

**FastAPI** — `BaseHTTPMiddleware` в каждом `main.py`:

```python
# feed_service/app/main.py  (аналогично в reactions и user-content)

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        token = correlation_id_var.set(cid)          # устанавливаем в контекст
        try:
            response = await call_next(request)      # обрабатываем запрос
        finally:
            correlation_id_var.reset(token)          # чистим после запроса
        response.headers["X-Correlation-ID"] = cid  # возвращаем клиенту
        return response
```

Логика:
- Если входящий запрос уже несёт `X-Correlation-ID` (пришёл от другого сервиса) — используем его.
- Если нет (первый запрос от браузера/клиента) — генерируем новый UUID.
- После запроса добавляем ID в ответ, чтобы клиент тоже мог его использовать.
- `token` + `reset()` гарантируют, что ContextVar очищается даже при исключении.

**Django** — классический синхронный middleware в [`news/middleware.py`](../news/middleware.py):

```python
class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = request.META.get("HTTP_X_CORRELATION_ID") or str(uuid.uuid4())
        token = correlation_id_var.set(cid)
        request.correlation_id = cid          # удобно для шаблонов/views
        try:
            response = self.get_response(request)
        finally:
            correlation_id_var.reset(token)
        response["X-Correlation-ID"] = cid
        return response
```

Middleware стоит вторым в стеке — сразу после Prometheus, до всего остального:

```python
# config/settings.py
MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'news.middleware.CorrelationIdMiddleware',   # ← здесь
    'django.middleware.security.SecurityMiddleware',
    ...
]
```

### Как ID попадает в каждую строку лога: Filter

Когда `logger.info("сообщение")` вызывается где-то глубоко в коде, нам нужно, чтобы `correlation_id` оказался в записи — и Filter решает это:

```python
# feed_service/app/logging_config.py

class CorrelationIdFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get("")  # читаем из контекста
        record.service = self.service_name
        return True
```

Filter вызывается автоматически для каждой лог-записи — не нужно писать `logger.info("msg", extra={"correlation_id": ...})` в каждом месте.

### Как ID передаётся между сервисами

Django вызывает микросервисы через [`news/services.py`](../news/services.py). Хелпер читает текущий ID и добавляет его в заголовки исходящего запроса:

```python
# news/services.py

def _cid_headers() -> Dict[str, str]:
    cid = correlation_id_var.get("")
    return {"X-Correlation-ID": cid} if cid else {}

# Используется во всех requests.get/post/put/delete:
response = requests.get(
    f"{self.base_url}/feed",
    params=params,
    headers=_cid_headers(),   # ← пробрасываем ID
    timeout=REQUEST_TIMEOUT
)
```

Принимающий FastAPI-сервис получает заголовок, middleware читает его и устанавливает в свой ContextVar — цепочка продолжается.

---

## Итоговая схема

```
Запрос от браузера
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Django CorrelationIdMiddleware                 │
│  читает X-Correlation-ID или генерирует UUID    │
│  correlation_id_var.set("a1b2-...")             │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
  feed-service  reactions   user-content
  middleware    middleware   middleware
  (то же самое) (то же самое) (то же самое)
        │            │            │
        ▼            ▼            ▼
  logger.info()  logger.info()  logger.info()
  CorrelationIdFilter читает correlation_id_var
        │
        ▼
{"correlation_id": "a1b2-...", "service": "feed-service", "message": "..."}
{"correlation_id": "a1b2-...", "service": "reactions-service", "message": "..."}
{"correlation_id": "a1b2-...", "service": "django-monolith", "message": "..."}
        │
        ▼
  grep 'a1b2-' — вся цепочка запроса
```

---

## Файлы, которые это реализуют

| Файл | Роль |
|---|---|
| `feed_service/app/logging_config.py` | ContextVar, Filter, setup_json_logging |
| `reactions-service/app/logging_config.py` | то же |
| `user_content_service/logging_config.py` | то же |
| `news/middleware.py` | Django middleware + Filter + JsonFormatter враппер |
| `feed_service/app/main.py` | вызов setup_json_logging + CorrelationIdMiddleware |
| `reactions-service/app/main.py` | то же |
| `user_content_service/main.py` | то же |
| `config/settings.py` | MIDDLEWARE + LOGGING для Django |
| `news/services.py` | `_cid_headers()` + заголовок во всех HTTP-вызовах |

## Тесты

Каждый сервис имеет `tests/integration/test_correlation.py` с проверками:

- middleware генерирует валидный UUID если ID не передан
- middleware возвращает тот же ID который получил
- два запроса получают разные ID (нет утечки контекста)
- filter добавляет `correlation_id` и `service` в LogRecord
- filter возвращает пустую строку если нет контекста (не падает)
