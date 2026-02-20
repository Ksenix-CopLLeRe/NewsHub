# User Content Service - Документация микросервиса

## Описание микросервиса

**User Content Service** — микросервис для управления персональными данными пользователя вокруг статей.

### Роль и ответственность

Микросервис отвечает за всё, что относится к персональным данным пользователя вокруг статей:

1. **Избранное (toggle по URL)** — добавление и удаление статей из избранного пользователя
2. **Комментарии к избранному** — создание, редактирование и удаление комментариев к сохраненным статьям
3. **Проверки «статья есть в избранном пользователя»** — для комментариев и отображения состояния кнопки "В избранное"

### База данных

Отдельная БД с таблицами:
- `favorite_articles` — избранные статьи пользователей
- `comments` — комментарии к избранным статьям

### Особенности реализации

- Каждый пользователь может добавить статью в избранное только один раз (уникальность по `user_id` и `url`)
- Комментарии можно оставлять только к статьям, которые есть в избранном пользователя
- Комментарии видны только автору комментария
- Поддержка пагинации для всех списков
- Формат дат: ISO 8601 в UTC
- Единый формат ошибок согласно стандартам проекта

---

## API Endpoints

### Base URL
```
http://localhost:8002
```

### 1. Избранное

#### POST /favorites/toggle
Добавить или удалить статью из избранного (toggle).

**Request Body:**
```json
{
  "user_id": 123,
  "url": "https://lenta.ru/news/2025/03/01/example/",
  "title": "Заголовок новости",
  "description": "Описание новости",
  "url_to_image": "https://example.com/image.jpg",
  "source_name": "Lenta.ru",
  "published_at": "2025-03-01T18:00:00Z"
}
```

**Response:**
```json
{
  "success": true,
  "is_favorite": true,
  "action": "added"
}
```

#### GET /favorites
Получить список избранных статей пользователя (с пагинацией).

**Query Parameters:**
- `user_id` (required) — ID пользователя
- `include_comments` (optional) — включить комментарии в ответ (default: false)
- `page` (optional) — номер страницы (default: 1)
- `size` (optional) — размер страницы (default: 10, max: 100)

**Response:**
```json
{
  "items": [
    {
      "id": 42,
      "user_id": 123,
      "url": "https://lenta.ru/news/2025/03/01/example/",
      "title": "Заголовок новости",
      "description": "Описание новости",
      "url_to_image": "https://example.com/image.jpg",
      "source_name": "Lenta.ru",
      "published_at": "2025-03-01T18:00:00Z",
      "added_at": "2025-03-01T19:00:00Z",
      "comments": []
    }
  ],
  "total": 42,
  "page": 1,
  "size": 10
}
```

#### GET /favorites/check/{url}
Проверить, есть ли статья в избранном пользователя.

**Path Parameters:**
- `url` — URL статьи (URL-encoded)

**Query Parameters:**
- `user_id` (required) — ID пользователя

**Response:**
```json
{
  "is_favorite": true,
  "article_id": 42
}
```

#### GET /favorites/urls
Получить список URL избранных статей пользователя (для быстрой проверки).

**Query Parameters:**
- `user_id` (required) — ID пользователя

**Response:**
```json
{
  "user_id": 123,
  "urls": [
    "https://lenta.ru/news/2025/03/01/example1/",
    "https://lenta.ru/news/2025/03/01/example2/"
  ],
  "total": 2
}
```

### 2. Комментарии

#### POST /favorites/{articleId}/comments
Добавить комментарий к избранной статье.

**Path Parameters:**
- `articleId` — ID избранной статьи

**Request Body:**
```json
{
  "user_id": 123,
  "text": "Это интересная статья!"
}
```

**Response:**
```json
{
  "success": true,
  "comment": {
    "id": 15,
    "article_id": 42,
    "user_id": 123,
    "text": "Это интересная статья!",
    "created_at": "2025-03-01T20:00:00Z"
  }
}
```

#### GET /favorites/{articleId}/comments
Получить комментарии к избранной статье (с пагинацией).

**Path Parameters:**
- `articleId` — ID избранной статьи

**Query Parameters:**
- `user_id` (required) — ID пользователя
- `page` (optional) — номер страницы (default: 1)
- `size` (optional) — размер страницы (default: 10, max: 100)

**Response:**
```json
{
  "items": [
    {
      "id": 15,
      "article_id": 42,
      "user_id": 123,
      "text": "Это интересная статья!",
      "created_at": "2025-03-01T20:00:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "size": 10
}
```

#### PUT /comments/{commentId}
Редактировать комментарий.

**Path Parameters:**
- `commentId` — ID комментария

**Request Body:**
```json
{
  "user_id": 123,
  "text": "Обновленный текст комментария"
}
```

**Response:**
```json
{
  "success": true,
  "comment": {
    "id": 15,
    "article_id": 42,
    "user_id": 123,
    "text": "Обновленный текст комментария",
    "created_at": "2025-03-01T20:00:00Z"
  }
}
```

#### DELETE /comments/{commentId}
Удалить комментарий.

**Path Parameters:**
- `commentId` — ID комментария

**Query Parameters:**
- `user_id` (required) — ID пользователя

**Response:**
```json
{
  "success": true
}
```

---

## Стандарты API

Микросервис следует общим стандартам проекта NewsHub:

- **Формат дат**: ISO 8601 в UTC (например, `2025-03-01T18:00:00Z`)
- **ID пользователей**: целые числа (integer)
- **ID новостей**: строки (string), содержащие URL новости
- **Пагинация**: параметры `page` (начиная с 1) и `size` (элементов на странице)
- **Формат ошибок**: единый формат с полями `error`, `code`, `details`

### Соответствие стандартам проекта

✅ Формат дат: ISO 8601 в UTC  
✅ ID пользователей: integer  
✅ ID новостей: string (URL)  
✅ Пагинация: `page` и `size`  
✅ Формат ошибок: `error`, `code`, `details`

---

## Статус коды ответов

- `200 OK` — успешная операция
- `201 Created` — ресурс успешно создан
- `400 Bad Request` — ошибка в данных запроса
- `401 Unauthorized` — не авторизован
- `403 Forbidden` — доступ запрещен
- `404 Not Found` — ресурс не найден

---

## Swagger документация

Полная OpenAPI спецификация доступна в файле:
```
openapi/user-content-service.yaml
```

Для просмотра Swagger UI можно использовать:
- [Swagger Editor](https://editor.swagger.io/) — загрузить файл `user-content-service.yaml`
- [Swagger UI](https://swagger.io/tools/swagger-ui/) — локальный запуск
- Интеграция в FastAPI приложение (при реализации микросервиса)

---

## Примеры использования

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8002"

# Добавить в избранное
response = requests.post(
    f"{BASE_URL}/favorites/toggle",
    json={
        "user_id": 123,
        "url": "https://lenta.ru/news/2025/03/01/example/",
        "title": "Заголовок новости",
        "description": "Описание новости",
        "source_name": "Lenta.ru",
        "published_at": "2025-03-01T18:00:00Z"
    }
)
print(response.json())

# Проверить наличие в избранном
response = requests.get(
    f"{BASE_URL}/favorites/check/https://lenta.ru/news/2025/03/01/example/",
    params={"user_id": 123}
)
print(response.json())

# Добавить комментарий
response = requests.post(
    f"{BASE_URL}/favorites/42/comments",
    json={
        "user_id": 123,
        "text": "Это интересная статья!"
    }
)
print(response.json())
```

### JavaScript (Fetch API)

```javascript
const BASE_URL = "http://localhost:8002";

// Добавить в избранное
fetch(`${BASE_URL}/favorites/toggle`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    user_id: 123,
    url: "https://lenta.ru/news/2025/03/01/example/",
    title: "Заголовок новости",
    description: "Описание новости",
    source_name: "Lenta.ru",
    published_at: "2025-03-01T18:00:00Z"
  })
})
.then(response => response.json())
.then(data => console.log(data));

// Проверить наличие в избранном
fetch(`${BASE_URL}/favorites/check/https://lenta.ru/news/2025/03/01/example/?user_id=123`)
  .then(response => response.json())
  .then(data => console.log(data));
```

---

## Интеграция с другими микросервисами

User Content Service взаимодействует с:
- **Feed Service** — получает информацию о новостях для добавления в избранное
- **Reactions Service** — может использоваться для проверки наличия статьи в избранном перед отображением реакций

---

## Быстрая справка

**Файл со Swagger спецификацией:** `openapi/user-content-service.yaml`

**Base URL микросервиса:** `http://localhost:8002`

**Всего эндпоинтов:** 8
- 4 для работы с избранным
- 4 для работы с комментариями

---

## Примечания для реализации

При реализации микросервиса на FastAPI рекомендуется:

1. Использовать отдельную БД (PostgreSQL, MySQL и т.д.)
2. Реализовать модели `FavoriteArticle` и `Comment` согласно схеме
3. Добавить аутентификацию через JWT токены или внутренние токены
4. Реализовать валидацию данных через Pydantic модели
5. Добавить логирование всех операций
6. Настроить CORS для взаимодействия с другими сервисами
7. Добавить rate limiting для защиты от злоупотреблений

---

## Структура файлов проекта

```
newshub/
├── openapi/
│   └── user-content-service.yaml    # OpenAPI спецификация для Swagger
├── docs/
│   └── USER_CONTENT_SERVICE.md       # Этот документ
└── API_STANDARDS.md                  # Стандарты API проекта
```

---

## Дополнительные материалы

- Стандарты API проекта: `API_STANDARDS.md`
- Пример аналогичного микросервиса: `openapi/reactions-service.yaml`