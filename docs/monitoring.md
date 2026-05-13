# Мониторинг: Prometheus + Grafana

## Общая схема работы

```
Сервисы (FastAPI / Django)
    │  expose /metrics
    ▼
Prometheus  ──scrape каждые 15с──►  собирает метрики
    │
    ▼
Grafana  ──PromQL запросы──►  рисует графики
```

1. **Каждый сервис** открывает эндпоинт `/metrics` — там числа в текстовом формате.
2. **Prometheus** раз в 15 секунд ходит на `/metrics` каждого сервиса и сохраняет данные у себя в базе (time-series).
3. **Grafana** подключена к Prometheus и делает PromQL-запросы, чтобы нарисовать дашборды.

---

## Как сервисы отдают метрики

### FastAPI сервисы (feed, reactions, user-content)

Используют библиотеку `prometheus-fastapi-instrumentator`.

**feed-service** — [`feed_service/app/main.py:4,121`](../feed_service/app/main.py)
```python
from prometheus_fastapi_instrumentator import Instrumentator
...
Instrumentator().instrument(app).expose(app)
```

**reactions-service** — [`reactions-service/app/main.py:2,59`](../reactions-service/app/main.py)
```python
from prometheus_fastapi_instrumentator import Instrumentator
...
Instrumentator().instrument(app).expose(app)
```

**user-content-service** — [`user_content_service/main.py:18,70`](../user_content_service/main.py)
```python
from prometheus_fastapi_instrumentator import Instrumentator
...
Instrumentator().instrument(app).expose(app)
```

Эти две строки делают всё автоматически:
- `.instrument(app)` — вешает middleware, который замеряет время каждого запроса
- `.expose(app)` — добавляет роут `GET /metrics`

Метрики, которые появляются автоматически:
| Метрика | Что измеряет |
|---|---|
| `http_requests_total` | счётчик запросов (по методу, статусу, пути) |
| `http_request_duration_seconds` | гистограмма времени ответа |
| `http_request_size_bytes` | размер входящих запросов |
| `http_response_size_bytes` | размер ответов |

---

### Django монолит (news)

Используют библиотеку `django-prometheus`.

**settings.py** — [`config/settings.py:30,41,50`](../config/settings.py)
```python
INSTALLED_APPS = [
    'django_prometheus',
    ...
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',  # первым
    ...
    'django_prometheus.middleware.PrometheusAfterMiddleware',   # последним
]
```

**urls.py** — [`config/urls.py:23`](../config/urls.py)
```python
path('', include('django_prometheus.urls')),
```

Это подключает `/metrics` и `/metrics/` роуты. Метрики называются иначе, чем в FastAPI:
| Метрика | Что измеряет |
|---|---|
| `django_http_requests_latency_including_middlewares_seconds` | время ответа (гистограмма) |
| `django_http_responses_total_by_status_total` | счётчик ответов по HTTP-статусу |

---

## Конфигурация Prometheus

Файл [`monitoring/prometheus.yml`](../monitoring/prometheus.yml) говорит Prometheus **куда ходить**:

```yaml
global:
  scrape_interval: 15s       # опрашивать каждые 15 секунд

scrape_configs:
  - job_name: 'django-monolith'
    static_configs:
      - targets: ['news:8000']     # имя контейнера в Docker сети
    metrics_path: /metrics

  - job_name: 'feed-service'
    static_configs:
      - targets: ['feed-service:8000']
    metrics_path: /metrics

  - job_name: 'reactions-service'
    static_configs:
      - targets: ['reactions-service:8000']
    metrics_path: /metrics

  - job_name: 'user-content-service'
    static_configs:
      - targets: ['user-content-service:8002']
    metrics_path: /metrics
```

> Важно: `news`, `feed-service` и т.д. — это имена сервисов из `docker-compose.all.yml`.
> Все контейнеры в одной Docker-сети `newshub-net`, поэтому имена резолвятся автоматически.

Prometheus хранит данные в volume `prometheus_data` и доступен на `localhost:9090`.

---

## Конфигурация Grafana

### Datasource (источник данных)

Файл [`monitoring/grafana/provisioning/datasources/prometheus.yml`](../monitoring/grafana/provisioning/datasources/prometheus.yml):

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090   # Grafana ходит к Prometheus внутри Docker-сети
    isDefault: true
```

"Provisioning" означает, что файл применяется автоматически при старте Grafana — не нужно настраивать вручную через UI.

### Дашборды

Файл [`monitoring/grafana/provisioning/dashboards/dashboard.yml`](../monitoring/grafana/provisioning/dashboards/dashboard.yml) говорит Grafana загрузить дашборды из папки `/etc/grafana/dashboards`.

Сам дашборд — [`monitoring/grafana/dashboards/newshub.json`](../monitoring/grafana/dashboards/newshub.json).

---

## Что показывает дашборд и как это работает

### 1. Availability — сервис UP или DOWN?

```promql
up{job="reactions-service"}
```

`up` — это специальная метрика самого Prometheus. Она равна:
- `1` — если Prometheus успешно скрейпнул `/metrics` в последний раз
- `0` — если не смог дотянуться (сервис упал, нет `/metrics`, таймаут)

Именно поэтому **отсутствие `/metrics` эндпоинта = DOWN** в Grafana.

### 2. Latency p95 / p50 — время ответа

```promql
histogram_quantile(
  0.95,
  sum(rate(http_request_duration_seconds_bucket{job=~"feed-service|..."}[1m])) by (job, le)
)
```

- `http_request_duration_seconds_bucket` — гистограмма: счётчики попаданий в бакеты (0.1s, 0.25s, 0.5s...)
- `rate(...[1m])` — скорость роста счётчика за последнюю минуту
- `histogram_quantile(0.95, ...)` — из этого считает 95-й перцентиль (p95 = 95% запросов быстрее этого значения)

### 3. Error Rate — 5xx ошибки в секунду

```promql
sum(rate(http_requests_total{job="feed-service", status_code=~"5.."}[1m])) or vector(0)
```

- Берёт счётчик запросов с кодами 5xx
- `rate(...[1m])` — переводит в "ошибок в секунду"
- `or vector(0)` — если метрики ещё нет, показывать 0 вместо "No data"

---

## Как это собрано в Docker Compose

Файл [`docker-compose.all.yml`](../docker-compose.all.yml):

```yaml
prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  networks:
    - newshub-net

grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  volumes:
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    - ./monitoring/grafana/dashboards:/etc/grafana/dashboards:ro
  depends_on:
    - prometheus
  networks:
    - newshub-net
```

Все сервисы в одной сети `newshub-net` — поэтому Prometheus достучится до сервисов по имени контейнера, а Grafana достучится до Prometheus по имени `prometheus`.

---

## Адреса в браузере

| Сервис | URL | Логин |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus UI | http://localhost:9090 | — |
| Метрики feed | http://localhost:8003/metrics | — |
| Метрики reactions | http://localhost:8004/metrics | — |
| Метрики user-content | http://localhost:8002/metrics | — |
| Метрики django | http://localhost:8000/metrics | — |

В Prometheus UI можно вводить PromQL запросы вручную: http://localhost:9090/graph

---

## Типичные проблемы

| Симптом | Причина | Решение |
|---|---|---|
| Сервис DOWN в Grafana | Нет `/metrics` эндпоинта | Добавить `Instrumentator().instrument(app).expose(app)` |
| Нет метрик после деплоя | Prometheus не перечитал конфиг | `docker compose restart prometheus` |
| Grafana "No data" | Datasource не настроен | Проверить `provisioning/datasources/prometheus.yml` |
| `up=0`, контейнер жив | Неверный порт или путь в `prometheus.yml` | Проверить `targets` и `metrics_path` |
