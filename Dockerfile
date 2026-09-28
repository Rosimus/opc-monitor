FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости приложения (все версии закреплены в requirements.txt),
# затем удаляем билд-инструменты (pip/setuptools/wheel) — приложению они в runtime
# не нужны, а их vendored-копии тянут CVE-2026-23949 и CVE-2026-24049.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pip setuptools wheel

# Непривилегированный пользователь с фиксированным UID/GID 1000
# (совпадает с runAsUser/runAsGroup в k8s-манифестах)
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser

# Копируем код приложения с правильными правами
COPY --chown=1000:1000 . .

# Создаём директории для данных
RUN mkdir -p /app/data /app/templates /app/static && \
    chown -R 1000:1000 /app

# Переключаемся на непривилегированного пользователя (числовой UID)
USER 1000:1000

# Порты: web, OPC UA, Prometheus metrics
EXPOSE 5000 4840 8001

# Health check (JSON-нотация — требование Hadolint DL3025)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"]

CMD ["python", "client.py"]
