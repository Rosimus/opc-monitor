# ============================================
# Stage 1: Builder — ставит зависимости в изолированный venv
# ============================================
FROM python:3.11-slim AS builder

# --copies: venv копирует python-бинарь, а не symlink
# (symlink сломается при COPY между stages)
RUN python -m venv --copies /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

COPY requirements.txt .
# hadolint ignore=DL3013
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pip setuptools wheel

# ============================================
# Stage 2: Runtime — минимальный образ с venv из builder
# ============================================
FROM python:3.11-slim

# Копируем готовый venv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Непривилегированный пользователь с фиксированным UID/GID 1000
# (совпадает с runAsUser/runAsGroup в k8s-манифестах)
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser

# Копируем код приложения с правильными правами
COPY --chown=1000:1000 . .

# Создаём директории для данных
RUN mkdir -p /app/data /app/templates /app/static && \
    chown -R 1000:1000 /app

# Удаляем setuptools/pip/wheel из базового Python (в /usr/local).
# Наш venv в /opt/venv самодостаточен, а vendored-копии setuptools тянут
# CVE-2026-23949 (jaraco.context) и CVE-2026-24049 (wheel).
RUN rm -rf /usr/local/lib/python3.11/site-packages/setuptools* \
           /usr/local/lib/python3.11/site-packages/pip* \
           /usr/local/lib/python3.11/site-packages/wheel*

# Переключаемся на непривилегированного пользователя (числовой UID)
USER 1000:1000

# Порты: web, OPC UA, Prometheus metrics
EXPOSE 5000 4840 8001

# Health check (JSON-нотация — требование Hadolint DL3025)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"]

CMD ["python", "client.py"]