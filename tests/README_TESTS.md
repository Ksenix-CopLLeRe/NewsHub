# Инструкция по запуску юнит-тестов

## Быстрый старт

```bash
# 1. Перейти в корень проекта
cd /path/to/project-root

# 2. Установить зависимости для тестов
pip install -r requirements-test.txt

# 3. Запустить все тесты
pytest

# 4. Запустить тесты конкретного сервиса
pytest tests/feed_service/
pytest tests/reactions_service/
pytest tests/user_content_service/
```

## Команды запуска

```bash
# === БАЗОВЫЕ КОМАНДЫ ===

# Запуск всех тестов
pytest

# Запуск с подробным выводом
pytest -v

# Запуск конкретного файла
pytest tests/feed_service/test_main.py

# Запуск конкретного теста
pytest tests/feed_service/test_main.py::TestCRUD::test_create_news


# === ФИЛЬТРАЦИЯ ПО МАРКЕРАМ ===

# Только unit-тесты (быстрые, без внешних зависимостей)
pytest -m unit

# Только integration-тесты (с реальными БД/API)
pytest -m integration

# Исключить медленные тесты
pytest -m "not slow"


# === ПОКРЫТИЕ КОДА ===

# С отчетом о покрытии
pytest --cov=feed_service --cov=reactions_service --cov=user_content_service

# С HTML отчетом
pytest --cov=. --cov-report=html
# Открыть htmlcov/index.html в браузере

# С минимальным порогом покрытия (упадет если <70%)
pytest --cov=. --cov-fail-under=70


# === ОСТАНОВ ПРИ ОШИБКАХ ===

# Остановиться после первой ошибки
pytest -x

# Остановиться после N ошибок
pytest --maxfail=3


# === ПАРАЛЛЕЛЬНЫЙ ЗАПУСК ===

# Запуск в 4 потоках
pytest -n 4

# Автоматическое определение числа потоков
pytest -n auto


# === ОТЛАДКА ===

# Показать print() в консоли
pytest -s

# Показать локальные переменные при ошибке
pytest -l

# Показать самые медленные тесты
pytest --durations=10
```
