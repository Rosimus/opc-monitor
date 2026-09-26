FROM python:3.11-slim

WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создание непривилегированного пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Копирование кода с правильными правами
COPY --chown=appuser:appuser . .

# Создание директорий для данных
RUN mkdir -p /app/data /app/templates /app/static && \
    chown -R appuser:appuser /app

# Переключение на непривилегированного пользователя
USER appuser

# Экспорт портов
EXPOSE 5000 4840 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["python", "client.py"]