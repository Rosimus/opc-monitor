# OPC Monitor — Runbook

Инструкция для инженера on-call по диагностике и восстановлению системы.

## 📋 Общая информация

| Параметр | Значение |
|----------|----------|
| **Namespace** | `opc-monitor` |
| **Helm release** | `opc-monitor` |
| **Образ** | `ghcr.io/rosimus/opc-monitor:sha-<commit>` |
| **Chart** | `helm/opc-monitor` |
| **CI/CD** | GitHub Actions + self-hosted runner |
| **GitOps** | ArgoCD (опционально) |

**Доступ к сервисам (порт-форвард):**

```bash
kubectl port-forward -n opc-monitor service/web 5000:5000
kubectl port-forward -n opc-monitor service/grafana 3000:3000
kubectl port-forward -n opc-monitor service/prometheus 9090:9090
kubectl port-forward -n opc-monitor service/alertmanager 9093:9093
kubectl port-forward -n opc-monitor service/jaeger 16686:16686
```

---

## 📊 SLO / SLI

| Метрика | SLI | SLO | Как измеряется |
|---------|-----|-----|----------------|
| **Доступность Web UI** | `up{job="opc-monitor"}` | ≥ 99% в месяц | Prometheus |
| **Доступность OPC Client** | `up{job="opc-client"}` | ≥ 99% в месяц | Prometheus |
| **Латентность API (p95)** | `histogram_quantile(0.95, api_latency_seconds_bucket)` | < 500 ms | Prometheus |
| **Задержка сбора данных** | `rate(opc_values[5m])` | > 0 | Prometheus |
| **RTO** | — | ≤ 5 минут | helm rollback |
| **RPO** | — | ≤ 24 часа | pg_dump ежедневно |

**Error Budget:** 1% недоступности в месяц = ~7.2 часа.

---

## 🚨 Алерты и реакции

### Alert: `ServiceDown`

**Severity:** critical

**Что значит:** сервис (`web`, `client`, `alertmanager`) не отвечает Prometheus > 1 минуты.

**Диагностика:**

```bash
# Статус подов
kubectl get pods -n opc-monitor

# Логи
kubectl logs -n opc-monitor deployment/web --tail=50

# События
kubectl describe pod -n opc-monitor -l app=web | tail -30
```

**Частые причины и фикс:**

| Симптом | Причина | Фикс |
|---------|---------|------|
| `CrashLoopBackOff` | ошибка конфига/секрета | `kubectl logs --previous` → исправить |
| `ImagePullBackOff` | нет образа в GHCR | проверить CI, `minikube image load` |
| `Pending` | не хватает ресурсов | `kubectl describe pod` → ноды |
| `Running 0/1` | readiness probe не проходит | `kubectl describe` → проверить `/health` |

**Восстановление:**

```bash
kubectl rollout restart deployment/web -n opc-monitor
# или
helm rollback opc-monitor -n opc-monitor
```

---

### Alert: `HighAlarmRate`

**Severity:** warning

**Что значит:** > 0.5 алертов/сек за 5 минут. Приложение стабильно генерирует тревоги.

**Это не проблема системы** — это значит реальная авария на оборудовании. Проверить:

```bash
# Последние алерты через API
kubectl exec -n opc-monitor deployment/web -- python -c "
import urllib.request, json
body = json.dumps({'username':'admin','password':'<ADMIN_PASSWORD>'}).encode()
req = urllib.request.Request('http://localhost:5000/api/auth/login', data=body, headers={'Content-Type':'application/json'})
token = json.loads(urllib.request.urlopen(req).read())['access_token']
req = urllib.request.Request('http://localhost:5000/api/alarms?limit=5', headers={'Authorization': f'Bearer {token}'})
print(urllib.request.urlopen(req).read().decode())
"
```

Или открыть Web UI → вкладка **Аварии**.

---

### Alert: `NoMeasurements`

**Severity:** warning

**Что значит:** OPC Client не отправляет измерения > 3 минут.

**Диагностика:**

```bash
# 1. Client запущен?
kubectl get pods -n opc-monitor -l app=client
kubectl logs -n opc-monitor deployment/client --tail=50

# 2. OPC Server доступен?
kubectl exec -n opc-monitor deployment/client -- python -c "import socket; s=socket.create_connection(('server', 4840), timeout=3); print('OPC OK'); s.close()"

# 3. БД доступна?
kubectl exec -n opc-monitor deployment/client -- python -c "import socket; s=socket.create_connection(('postgres', 5432), timeout=3); print('PG OK'); s.close()"
```

**Частые причины:**

| Симптом | Причина | Фикс |
|---------|---------|------|
| `OPC server unavailable` | server упал | `kubectl rollout restart deployment/server` |
| `PostgreSQL connection failed` | БД упала | `kubectl get pod postgres-0`, `kubectl logs postgres-0` |
| `waiting-for-postgres` в initContainer | БД долго стартует | подождать, если > 5 мин — проблема в postgres |
| `Redis недоступен` | Redis упал | `kubectl rollout restart deployment/redis` |

---

### Alert: `HighAPILatency`

**Severity:** warning

**Что значит:** p95 латентности API > 1 секунды.

**Диагностика:**

```bash
# Проверить метрики
kubectl port-forward -n opc-monitor service/prometheus 9090:9090
# Открыть http://localhost:9090 → запрос:
# histogram_quantile(0.95, api_latency_seconds_bucket)

# Медленные запросы — Jaeger
kubectl port-forward -n opc-monitor service/jaeger 16686:16686
# Открыть http://localhost:16686 → service=opc-monitor-web → найти span > 1s
```

**Частые причины:**

| Симптом | Причина | Фикс |
|---------|---------|------|
| БД медленная | нет индексов / тяжёлый запрос | `EXPLAIN ANALYZE`, добавить индекс |
| Redis отвалился | кэш не работает | `kubectl get pod -l app=redis` |
| Memory pressure | под в OOM | увеличить `resources.limits.memory` в values |

---

## 🔧 Типовые операции

### Деплой новой версии

Автоматически через CI/CD при push в `main`:
1. CI собирает образ → GHCR (`sha-<commit>`)
2. CD деплоит через Helm → minikube

**Ручной деплой (если CD упал):**

```bash
helm upgrade --install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --values ./helm/opc-monitor/values-prod.yaml \
  --values ./helm/opc-monitor/values-secrets.yaml \
  --force-conflicts \
  --timeout 3m
```

### Откат

```bash
# История
helm history opc-monitor -n opc-monitor

# Откат на предыдущую
helm rollback opc-monitor -n opc-monitor

# Откат на конкретную ревизию
helm rollback opc-monitor -n opc-monitor 15
```

### Перезапуск сервиса

```bash
# Один сервис
kubectl rollout restart deployment/web -n opc-monitor

# Все
kubectl rollout restart deployment -n opc-monitor
kubectl rollout restart statefulset/postgres -n opc-monitor
kubectl rollout restart daemonset/promtail -n opc-monitor
```

### Масштабирование web

```bash
kubectl scale deployment/web --replicas=3 -n opc-monitor
```

### Обновление конфига

```bash
# 1. Правишь config.yaml
# 2. Применяешь
kubectl create configmap opc-config --from-file=config.yaml -n opc-monitor --dry-run=client -o yaml | kubectl apply -f -
# 3. Рестарт подов
kubectl rollout restart deployment/web deployment/client deployment/server -n opc-monitor
```

---

## 🐛 Troubleshooting (частые проблемы)

### Web не стартует: `RuntimeError: JWT_SECRET_KEY must be set`

**Причина:** секрет `opc-secrets` пуст или содержит placeholder.

**Фикс:**

```bash
# Проверить
kubectl get secret opc-secrets -n opc-monitor -o jsonpath="{.data.JWT_SECRET_KEY}" | %{ [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

# Пересоздать
$jwt = python -c "import secrets; print(secrets.token_hex(32))"
kubectl create secret generic opc-secrets -n opc-monitor \
  --from-literal=JWT_SECRET_KEY=$jwt \
  --from-literal=POSTGRES_PASSWORD=<password> \
  --from-literal=ADMIN_PASSWORD=<password> \
  --from-literal=GRAFANA_PASSWORD=<password> \
  --from-literal=ADMIN_USER=admin \
  --from-literal=POSTGRES_USER=opc_user \
  --from-literal=POSTGRES_DB=opc_monitor \
  --from-literal=EMAIL_PASSWORD="" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/web deployment/client -n opc-monitor
```

### `Control server error: [Errno 30] Read-only file system: '/home/appuser'`

**Причина:** gunicorn 26.x control server хочет unix-socket в `$HOME`, а rootfs read-only.

**Фикс:** проверить, что в `command` есть `--no-control`:
```
command: ["gunicorn", "-k", "gthread", "-w", "2", "web_app:app", "-b", "0.0.0.0:5000", "--no-control"]
```

### `PermissionError: Read-only file system` в `/app`

**Причина:** приложение пишет за пределами `/tmp`.

**Фикс:**
1. Проверить, что `/tmp` смонтирован как emptyDir:
   ```
   volumeMounts:
     - name: tmp
       mountPath: /tmp
   ```
2. Если пишет в другое место — либо отключить `readOnlyRootFilesystem: true`, либо смонтировать этот путь как emptyDir.

### `waiting-for-postgres` в логах initContainer бесконечно

**Причина:** postgres не отвечает на 5432.

**Фикс:**
1. `kubectl get pod postgres-0 -n opc-monitor` — он вообще запущен?
2. `kubectl logs postgres-0 -n opc-monitor --tail=30`
3. Проверить `securityContext` postgres — если UID не совпадает с владельцем PVC:
   ```
   Permission denied: /var/lib/postgresql/data
   ```
   → `kubectl delete pvc postgres-data-postgres-0` (потеря данных!) или убрать `runAsUser` из манифеста.

### Redis недоступен

**Причина:** сервис `redis` не резолвится или pod упал.

**Фикс:**
```bash
kubectl get svc redis -n opc-monitor
kubectl get pod -l app=redis -n opc-monitor
kubectl rollout restart deployment/redis -n opc-monitor
```

### Health-check падает: `429 Too Many Requests`

**Причина:** rate limiter блокирует `/health`.

**Фикс:** проверить, что в `web_app.py`:
```python
default_limits_exempt_when=lambda: request.endpoint in ('health', 'metrics')
```

---

## 🗄️ База данных

### Подключение

```bash
kubectl exec -it -n opc-monitor postgres-0 -- psql -U opc_user -d opc_monitor
```

### Проверка прав

```sql
-- opc_user НЕ суперюзер
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname='opc_user';
-- Ожидаемо: opc_user | f | f | f

-- Привилегии на таблицы
SELECT grantee, privilege_type, table_name
FROM information_schema.role_table_grants
WHERE table_schema='public' AND grantee='opc_user'
ORDER BY table_name, privilege_type;
-- Ожидаемо: только INSERT, SELECT, UPDATE, DELETE (без TRUNCATE/REFERENCES/TRIGGER)
```

### Если права сброшены (например, после пересоздания PVC)

**Автоматически:** init-скрипт `postgres-init` ConfigMap сработает при первичной инициализации.

**Вручную:**
```sql
ALTER USER opc_user NOSUPERUSER NOCREATEROLE NOCREATEDB;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE TRUNCATE, REFERENCES, TRIGGER ON TABLES FROM opc_user;
```

### Бэкап

```bash
kubectl exec -n opc-monitor postgres-0 -- pg_dump -U opc_user opc_monitor > backup_$(date +%Y%m%d).sql
```

### Восстановление

```bash
kubectl exec -i -n opc-monitor postgres-0 -- psql -U opc_user -d opc_monitor < backup_20260101.sql
```

### Размер БД

```sql
SELECT pg_size_pretty(pg_database_size('opc_monitor'));
SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;
```

---

## 🔑 Секреты

### Смена паролей

**1. JWT_SECRET_KEY** (инвалидирует все токены):

```bash
$newJwt = python -c "import secrets; print(secrets.token_hex(32))"
kubectl patch secret opc-secrets -n opc-monitor -p "{`"data`":{`"JWT_SECRET_KEY`":`"$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($newJwt)))`"}}"
kubectl rollout restart deployment/web deployment/client -n opc-monitor
```

**2. ADMIN_PASSWORD:**

```bash
$newPass = "<новый пароль>"
kubectl patch secret opc-secrets -n opc-monitor -p "{`"data`":{`"ADMIN_PASSWORD`":`"$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($newPass)))`"}}"
kubectl rollout restart deployment/web -n opc-monitor
```

**3. POSTGRES_PASSWORD** — сначала в БД, потом в секрете:

```bash
# 1. Изменить в БД
kubectl exec -n opc-monitor postgres-0 -- psql -U opc_user -d opc_monitor -c "ALTER USER opc_user WITH PASSWORD 'новый_пароль';"

# 2. Обновить Secret
kubectl patch secret opc-secrets -n opc-monitor -p '{"data":{"POSTGRES_PASSWORD":"<base64>"}}'

# 3. Рестарт
kubectl rollout restart deployment/web deployment/client -n opc-monitor
kubectl delete pod postgres-0 -n opc-monitor
```

### GitHub Secrets

Для CI/CD используются secrets (Settings → Secrets and variables → Actions):
- `JWT_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `ADMIN_PASSWORD`
- `GRAFANA_PASSWORD`

**При смене пароля** — обновить и в k8s Secret, и в GitHub Secrets.

---

## 📈 Observability

### Grafana

```bash
kubectl port-forward -n opc-monitor service/grafana 3000:3000
# http://localhost:3000
# admin / <GRAFANA_PASSWORD>
```

**Дашборд:** OPC Monitor → 5 панелей (значения, статус, алерты, RPS, latency).

### Prometheus

```bash
kubectl port-forward -n opc-monitor service/prometheus 9090:9090
# http://localhost:9090
```

**Полезные запросы:**
- `up` — какие сервисы живы
- `rate(api_requests_total[5m])` — RPS
- `histogram_quantile(0.95, api_latency_seconds_bucket)` — p95 latency
- `opc_values` — текущие значения параметров

### Loki (логи)

В Grafana → **Explore → Loki**:

```logql
{job="opc-monitor"} |= "Measurement"
{job="opc-monitor"} |= "ERROR"
{job="opc-monitor"} | json | trace_id="<trace_id>"
```

### Jaeger (трейсы)

```bash
kubectl port-forward -n opc-monitor service/jaeger 16686:16686
# http://localhost:16686
```

**Service:** `opc-monitor-web`, `opc-monitor-client`

### Alertmanager

```bash
kubectl port-forward -n opc-monitor service/alertmanager 9093:9093
# http://localhost:9093
```

---

## 🚑 Аварийное восстановление

### Полная переустановка

```bash
# 1. Удалить релиз (PVC остаются)
helm uninstall opc-monitor -n opc-monitor

# 2. При необходимости — удалить PVC (ПОТЕРЯ ДАННЫХ)
kubectl delete pvc --all -n opc-monitor

# 3. Переустановить
helm install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --values ./helm/opc-monitor/values-prod.yaml \
  --values ./helm/opc-monitor/values-secrets.yaml \
  --timeout 3m
```

### Проверка всего стека

```bash
# 1. Все поды Running
kubectl get pods -n opc-monitor

# 2. Health
kubectl exec -n opc-monitor deployment/web -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:5000/health').read().decode())"

# 3. БД/Redis/OPC
kubectl exec -n opc-monitor deployment/client -- python -c "
import socket
for name, host, port in [('postgres','postgres',5432), ('redis','redis',6379), ('opc','server',4840)]:
    try:
        s = socket.create_connection((host, port), timeout=3); s.close()
        print(f'{name}: OK')
    except Exception as e:
        print(f'{name}: FAIL {e}')
"
```

### Если кластер потерян

Minikube пересоздать:
```bash
minikube delete
minikube start --driver=docker --memory=6144 --cpus=4
# Далее — terraform/helm по документации
```

---

## 📞 Контакты

**Автор:** Rosimus
**Email:** rosimus854@gmail.com
**GitHub:** [@Rosimus](https://github.com/Rosimus)
**Issues:** https://github.com/Rosimus/opc-monitor/issues