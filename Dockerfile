FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Жёстко удаляем Redis и все его файлы
RUN pip uninstall -y redis redis-py 2>/dev/null || true
RUN rm -rf /usr/local/lib/python3.11/site-packages/redis* || true
RUN rm -rf /usr/local/lib/python3.11/site-packages/redis-*.dist-info || true
RUN find /usr/local/lib -name "*redis*" -exec rm -rf {} + 2>/dev/null || true

COPY . .

RUN mkdir -p /app/data /app/templates /app/static

EXPOSE 5000 4840 8001

CMD ["python", "client.py"]