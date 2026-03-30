# Используем зеркало Microsoft (вместо Docker Hub)
FROM mcr.microsoft.com/devcontainers/python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код сервиса, чтобы внутри контейнера были app/*
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]