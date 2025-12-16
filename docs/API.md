# API Documentation

## Base URL
```
http://127.0.0.1:8000
```

## Authentication

Все API endpoints (кроме публичных страниц) требуют аутентификации пользователя через Django сессии. Пользователь должен быть залогинен в системе.

Для AJAX-запросов необходимо включить CSRF токен в заголовках:
```
X-CSRFToken: <csrf_token>
```

CSRF токен можно получить из cookie `csrftoken` или из формы на странице.

---

## Endpoints

### 1. Toggle Favorite (Добавить/удалить из избранного)

**Endpoint:** `POST /api/toggle-favorite/`

**Description:** Добавляет статью в избранное или удаляет её, если она уже в избранном.

**Authentication:** Required

**Request Headers:**
```
Content-Type: application/json
X-CSRFToken: <csrf_token>
```

**Request Body:**
```json
{
  "url": "https://lenta.ru/news/2025/01/15/example/",
  "title": "Заголовок новости",
  "description": "Описание новости",
  "urlToImage": "https://example.com/image.jpg",
  "source": {
    "name": "Lenta.ru"
  },
  "publishedAt": "2025-01-15T10:00:00Z"
}
```

**Response (Success):**
```json
{
  "success": true,
  "is_favorite": true
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "URL статьи не указан"
}
```

**Status Codes:**
- `200 OK` - Успешная операция
- `400 Bad Request` - Некорректные данные
- `401 Unauthorized` - Пользователь не авторизован
- `500 Internal Server Error` - Ошибка сервера

---

### 2. Add Reaction (Добавить/изменить реакцию)

**Endpoint:** `POST /api/add-reaction/`

**Description:** Добавляет реакцию на новость, изменяет существующую реакцию или удаляет её (если та же реакция выбрана повторно).

**Authentication:** Required

**Request Headers:**
```
Content-Type: application/json
X-CSRFToken: <csrf_token>
```

**Request Body:**
```json
{
  "url": "https://lenta.ru/news/2025/01/15/example/",
  "reaction_type": "important"
}
```

**Reaction Types:**
- `important` - 🔥 важно
- `interesting` - 🤔 интересно
- `shocking` - 😱 шокирует
- `useful` - 💡 полезно
- `liked` - ❤️ нравится

**Response (Success):**
```json
{
  "success": true,
  "reaction_type": "important",
  "reactions_count": {
    "important": 5,
    "interesting": 3,
    "liked": 2
  }
}
```

**Response (Reaction Cancelled):**
```json
{
  "success": true,
  "reaction_type": null,
  "reactions_count": {
    "interesting": 3,
    "liked": 2
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Неверный тип реакции"
}
```

**Status Codes:**
- `200 OK` - Успешная операция
- `400 Bad Request` - Некорректные данные
- `401 Unauthorized` - Пользователь не авторизован
- `500 Internal Server Error` - Ошибка сервера

---

### 3. Add Comment (Добавить комментарий)

**Endpoint:** `POST /api/add-comment/`

**Description:** Добавляет комментарий к избранной статье пользователя.

**Authentication:** Required

**Request Headers:**
```
Content-Type: application/json
X-CSRFToken: <csrf_token>
```

**Request Body:**
```json
{
  "article_id": 1,
  "text": "Это интересная статья!"
}
```

**Response (Success):**
```json
{
  "success": true,
  "comment": {
    "id": 1,
    "text": "Это интересная статья!",
    "created_at": "15.01.2025 10:00"
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Текст комментария не может быть пустым"
}
```

**Status Codes:**
- `200 OK` - Успешная операция
- `400 Bad Request` - Некорректные данные
- `401 Unauthorized` - Пользователь не авторизован
- `404 Not Found` - Статья не найдена
- `500 Internal Server Error` - Ошибка сервера

---

### 4. Edit Comment (Редактировать комментарий)

**Endpoint:** `POST /api/edit-comment/<comment_id>/`

**Description:** Редактирует существующий комментарий пользователя.

**Authentication:** Required

**Request Headers:**
```
Content-Type: application/json
X-CSRFToken: <csrf_token>
```

**Request Body:**
```json
{
  "text": "Обновленный текст комментария"
}
```

**Response (Success):**
```json
{
  "success": true,
  "comment": {
    "id": 1,
    "text": "Обновленный текст комментария",
    "created_at": "15.01.2025 10:00"
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Текст комментария не может быть пустым"
}
```

**Status Codes:**
- `200 OK` - Успешная операция
- `400 Bad Request` - Некорректные данные
- `401 Unauthorized` - Пользователь не авторизован
- `404 Not Found` - Комментарий не найден
- `500 Internal Server Error` - Ошибка сервера

---

### 5. Delete Comment (Удалить комментарий)

**Endpoint:** `POST /api/delete-comment/<comment_id>/`

**Description:** Удаляет комментарий пользователя.

**Authentication:** Required

**Request Headers:**
```
Content-Type: application/json
X-CSRFToken: <csrf_token>
```

**Request Body:** (пустое тело запроса)

**Response (Success):**
```json
{
  "success": true
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Комментарий не найден"
}
```

**Status Codes:**
- `200 OK` - Успешная операция
- `401 Unauthorized` - Пользователь не авторизован
- `404 Not Found` - Комментарий не найден
- `500 Internal Server Error` - Ошибка сервера

---

## Postman Collection

Для импорта в Postman используйте следующий JSON:

```json
{
  "info": {
    "name": "NewsHub API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Toggle Favorite",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-CSRFToken",
            "value": "{{csrf_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"url\": \"https://lenta.ru/news/example/\",\n  \"title\": \"Заголовок\",\n  \"description\": \"Описание\",\n  \"urlToImage\": \"\",\n  \"source\": {\"name\": \"Lenta.ru\"},\n  \"publishedAt\": \"2025-01-15T10:00:00Z\"\n}"
        },
        "url": {
          "raw": "http://127.0.0.1:8000/api/toggle-favorite/",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "toggle-favorite", ""]
        }
      }
    },
    {
      "name": "Add Reaction",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-CSRFToken",
            "value": "{{csrf_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"url\": \"https://lenta.ru/news/example/\",\n  \"reaction_type\": \"important\"\n}"
        },
        "url": {
          "raw": "http://127.0.0.1:8000/api/add-reaction/",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "add-reaction", ""]
        }
      }
    },
    {
      "name": "Add Comment",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-CSRFToken",
            "value": "{{csrf_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"article_id\": 1,\n  \"text\": \"Комментарий\"\n}"
        },
        "url": {
          "raw": "http://127.0.0.1:8000/api/add-comment/",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "add-comment", ""]
        }
      }
    },
    {
      "name": "Edit Comment",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-CSRFToken",
            "value": "{{csrf_token}}"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"text\": \"Обновленный комментарий\"\n}"
        },
        "url": {
          "raw": "http://127.0.0.1:8000/api/edit-comment/1/",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "edit-comment", "1", ""]
        }
      }
    },
    {
      "name": "Delete Comment",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          },
          {
            "key": "X-CSRFToken",
            "value": "{{csrf_token}}"
          }
        ],
        "url": {
          "raw": "http://127.0.0.1:8000/api/delete-comment/1/",
          "protocol": "http",
          "host": ["127", "0", "0", "1"],
          "port": "8000",
          "path": ["api", "delete-comment", "1", ""]
        }
      }
    }
  ]
}
```

## Insomnia Collection

Для импорта в Insomnia сохраните файл `NewsHub_API.json` с содержимым выше и импортируйте через меню Import.

## Примеры использования

### JavaScript (Fetch API)

```javascript
// Toggle Favorite
fetch('/api/toggle-favorite/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken')
  },
  body: JSON.stringify({
    url: 'https://lenta.ru/news/example/',
    title: 'Заголовок',
    description: 'Описание',
    urlToImage: '',
    source: {name: 'Lenta.ru'},
    publishedAt: '2025-01-15T10:00:00Z'
  })
})
.then(response => response.json())
.then(data => console.log(data));

// Add Reaction
fetch('/api/add-reaction/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCookie('csrftoken')
  },
  body: JSON.stringify({
    url: 'https://lenta.ru/news/example/',
    reaction_type: 'important'
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

### Python (requests)

```python
import requests

# Получить CSRF токен (нужно сначала залогиниться)
session = requests.Session()
response = session.get('http://127.0.0.1:8000/')
csrf_token = session.cookies.get('csrftoken')

# Toggle Favorite
response = session.post(
    'http://127.0.0.1:8000/api/toggle-favorite/',
    json={
        'url': 'https://lenta.ru/news/example/',
        'title': 'Заголовок',
        'description': 'Описание',
        'urlToImage': '',
        'source': {'name': 'Lenta.ru'},
        'publishedAt': '2025-01-15T10:00:00Z'
    },
    headers={'X-CSRFToken': csrf_token}
)
print(response.json())
```

