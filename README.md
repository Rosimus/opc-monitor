# OPC Monitor

[![CI](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml)
[![CD](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml)
[![Container Registry](https://img.shields.io/badge/registry-ghcr.io-blue)](https://github.com/Rosimus/opc-monitor/pkgs/container/opc-monitor)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-k3s%20%7C%20minikube-326CE5)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/helm-3.12+-0F1689)](https://helm.sh/)
[![ArgoCD](https://img.shields.io/badge/argocd-GitOps-orange)](https://argo-cd.readthedocs.io/)
[![Tests](https://img.shields.io/badge/tests-41%20passed-brightgreen)](#-тестирование)
[![Security](https://img.shields.io/badge/security-audited-brightgreen)](SECURITY.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Система мониторинга промышленного оборудования на OPC UA с веб-интерфейсом, алертами, аналитикой и полным observability-стеком.

## ✨ Возможности

### Приложение
- 📊 **Real-time мониторинг** 8 параметров (температура, давление, влажность, вибрация, ток, скорость, уровень, частота)
- 🎬 **Реалистичный симулятор PLC** — random walk, mean reversion, суточные колебания, случайные и каскадные аварии
- 🚨 **Многоуровневые алерты** (Warning / Alarm) с Email и Telegram уведомлениями
- 📈 **Графики в реальном времени** — Chart.js с пороговыми линиями
- 🔐 **JWT-аутентификация** веб-интерфейса
- 📥 **Экспорт данных** в CSV и Excel
- 🎯 **REST API** с автогенерируемой документацией (Swagger)

### Observability
- 📉 **Метрики:** Prometheus + Grafana as code (5 панелей)
- 🔔 **Алерты:** Alertmanager с 4 правилами
- 📋 **Логи:** Loki + Promtail (сбор со всех подов)
- 🔍 **Трейсы:** OpenTelemetry + Jaeger (distributed tracing)
- 🔗 **Корреляция:** trace_id в логах + переход Loki ↔ Jaeger одним кликом

### DevOps
- 🐳 **Docker-образ** с автоматической сборкой
- ☸️ **Kubernetes** через kubectl / Helm
- ⛵ **Helm-чарт** с параметризацией под staging/prod
- 🔑 **Управление секретами** через GitHub Secrets + `values-secrets.yaml`
- 🌩️ **Terraform** — IaC для Yandex Cloud (k3s, managed PostgreSQL)
- 🔄 **CI/CD** через GitHub Actions с self-hosted runner
- 🔀 **ArgoCD** — GitOps-подход (pull-модель деплоя)
- ✅ **41 тест** (29 unit + 12 integration) в CI pipeline
- 📦 **GHCR** — автоматическая загрузка образов
- 🛡️ **Security Hardened** — полный аудит (SAST/SCA/JWT/ZAP/K8s/Docker/Terraform), 0 CVE, 0 находок Bandit/Hadolint

## 🏗️ Архитектура

Проект — это **распределённая система из 9 контейнеров**, объединённых общей сетью и слоем хранения. Каждый сервис выполняет одну функцию.

```
┌──────────────────────────────────────────────────────────┐
│                    OPC UA Server (PLC)                   │
│                    opc.tcp://server:4840                 │
└───────────────────────────┬──────────────────────────────┘
                            │ OPC UA (TCP)
                            ▼
┌──────────────────────────────────────────────────────────┐
│              OPC Client (Python + opcua)                 │
│  • Сбор данных каждые 5 секунд                           │
│  • Проверка порогов                                      │
│  • Отправка алертов (Email, Telegram)                    │
│  • Метрики Prometheus на :8001                           │
│  • OTel трейсы в Jaeger                                  │
└───────────────────────────┬──────────────────────────────┘
                            │ SQLAlchemy + Redis
                            ▼
┌──────────────────────────────────────────────────────────┐
│            PostgreSQL 15 + Redis Cache                   │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│         Web App (Flask + Gunicorn)                       │
│  • REST API с JWT-аутентификацией                        │
│  • Web UI (Chart.js, dark/light тема)                    │
│  • Security headers (Talisman) + Rate limiting           │
│  • Метрики Prometheus на :5000/metrics                   │
│  • OTel трейсы в Jaeger                                  │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│         Observability Stack                              │
│  • Prometheus + Alertmanager (метрики, алерты)           │
│  • Loki + Promtail (централизованные логи)               │
│  • Jaeger (distributed tracing)                          │
│  • Grafana (единый UI: metrics + logs + traces)          │
└──────────────────────────────────────────────────────────┘
```

## 🛠️ Стек технологий

| Категория | Технологии |
|-----------|------------|
| **Backend** | Python 3.11, Flask, SQLAlchemy, Gunicorn, structlog |
| **Frontend** | Vanilla JS, Chart.js, Socket.IO client |
| **База данных** | PostgreSQL 15, Redis 7 (кэш) |
| **Аутентификация** | JWT (flask-jwt-extended) |
| **Безопасность** | Flask-Talisman, Flask-Limiter, Trivy, Bandit, Semgrep, Checkov |
| **Оркестрация** | Kubernetes (k3s / Minikube), Helm 3 |
| **GitOps** | ArgoCD |
| **CI/CD** | GitHub Actions, GHCR, self-hosted runner, Dependabot |
| **Metrics** | Prometheus, Alertmanager, Grafana |
| **Logs** | Loki, Promtail |
| **Traces** | OpenTelemetry SDK, Jaeger |
| **IaC** | Terraform (Yandex Cloud) |
| **Тесты** | pytest, pytest-cov, pytest-mock |

## 📸 Скриншоты

### 📊 Real-time Dashboard

![Dashboard](docs/screenshots/dashboard.png)

*Real-time мониторинг 8 параметров с карточками статусов, графиками и пороговыми линиями*

### 🚨 История аварий

![Alerts](docs/screenshots/alerts.png)

*Полная история аварий с фильтрацией по времени, параметрам и статусу*

### 📈 Grafana — Metrics

![Grafana](docs/screenshots/grafana.png)

*Provisioned дашборд с 5 панелями: значения параметров, статус системы, алерты, RPS и латентность API*

### 🔍 Jaeger — Distributed Tracing

![Jaeger](docs/screenshots/jaeger.png)

*Waterfall-диаграмма HTTP-запроса `/api/latest`: Flask-обработчик → коннект к БД → SQL-запрос*

### 🔗 Корреляция логов и трейсов

![Trace Correlation](docs/screenshots/trace-correlation.png)

*Split view: слева логи в Loki с trace_id, справа трейс в Jaeger. Переход одним кликом*

### ✅ CI/CD Pipeline

![Actions](docs/screenshots/actions.png)

*GitHub Actions: тесты → сборка → Trivy scan → деплой через Helm*

## 🚀 Быстрый старт

### Предварительные требования

- **Windows 10/11** с WSL2 (или Linux/macOS)
- **Docker Desktop** 4.20+
- **Minikube** 1.30+
- **kubectl** 1.27+
- **Helm** 3.12+

### Запуск через Docker Compose

```bash
git clone https://github.com/Rosimus/opc-monitor.git
cd opc-monitor
copy .env.example .env
docker-compose up -d
```

**Доступ**: http://localhost:5000

### Запуск в Kubernetes через Helm

```bash
minikube start --driver=docker --memory=6144 --cpus=4
docker build -t opc-monitor:latest .
minikube image load opc-monitor:latest

helm install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --create-namespace \
  --values ./helm/opc-monitor/values-prod.yaml
```

**Проброс портов:**

```bash
kubectl port-forward -n opc-monitor service/web 5000:5000
kubectl port-forward -n opc-monitor service/grafana 3000:3000
kubectl port-forward -n opc-monitor service/jaeger 16686:16686
kubectl port-forward -n opc-monitor service/prometheus 9090:9090
kubectl port-forward -n opc-monitor service/alertmanager 9093:9093
```

**Доступ:**
- Web UI: http://localhost:5000
- Grafana: http://localhost:3000 (admin / admin)
- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

## 🔄 CI/CD Pipeline

Проект использует **полностью автоматизированный CI/CD** через GitHub Actions.

### CI — Test, Build & Push

При каждом push в `main`:
1. ✅ **Run Tests** — 41 тест (29 unit + 12 integration) + coverage report
2. ✅ Сборка Docker-образа
3. ✅ Загрузка в GitHub Container Registry (GHCR)
4. ✅ **Trivy scan** — проверка на уязвимости (CRITICAL/HIGH)
5. ✅ Теги: `latest`, `sha-<commit>`, `<branch>`

### CD — Deploy to Minikube

После успешного CI:
1. ✅ Self-hosted runner получает задачу
2. ✅ Скачивает образ из GHCR
3. ✅ Загружает в Minikube
4. ✅ Выполняет `helm upgrade --install` (атомарно)
5. ✅ Подставляет секреты из GitHub Secrets (если заданы)
6. ✅ Проверяет готовность через `kubectl rollout status`

**Время от `git push` до работающего приложения: ~60 секунд** ⚡

### 🤖 Dependabot

Автоматическое обновление зависимостей и SHA-пины GitHub Actions (`.github/dependabot.yml`):

- **github-actions** — еженедельно, пин на commit SHA (защита от supply-chain атак)
- **pip** — Python-пакеты из `requirements.txt`
- **docker** — базовый образ `python:3.11-slim`
- **terraform** — Yandex Cloud provider

Cooldown 7 дней — новые версии не подхватываются сразу, ждём проверки сообществом.

### GitOps с ArgoCD

Проект поддерживает **GitOps-подход** через ArgoCD. ArgoCD отслеживает helm-чарт в Git и синхронизирует его с кластером (pull-модель).

**Установка ArgoCD в Minikube:**

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Пароль admin
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Проброс портов
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

**Application манифест** — `argocd/application.yaml`.

### Откат

```bash
# Через Helm
helm history opc-monitor -n opc-monitor
helm rollback opc-monitor -n opc-monitor

# Через ArgoCD UI
# Открыть приложение → History and Rollback → выбрать ревизию
```

## 🔍 Observability

### Метрики (Prometheus + Grafana)

- **Prometheus** собирает метрики с web и client (`/metrics`)
- **Grafana** показывает 5 панелей: значения параметров, статус, счётчик алертов, RPS, латентность API
- Дашборд провизионится как код через ConfigMap

### Логи (Loki + Promtail)

- **Promtail** собирает логи со всех подов через `/var/log/containers/`
- **Loki** хранит логи 7 дней
- **Grafana Explore → Loki** — поиск по логам

### Трейсы (OpenTelemetry + Jaeger)

- **OTel SDK** инструментирует Flask, SQLAlchemy, requests
- **Jaeger** принимает трейсы через OTLP (gRPC)
- Каждый запрос оставляет трейс со спанами (HTTP → SQL → Redis)

### Корреляция logs ↔ traces

Каждая запись лога содержит `trace_id`. В Grafana:

1. **Explore → Loki** → запрос `{job="opc-monitor"} |= "Measurement"`.
2. Раскрой лог → поле **TraceID** → клик → откроется трейс в Jaeger.
3. Из Jaeger → **Logs** → переход обратно в Loki по времени спана.

### Алерты (Alertmanager)

4 правила в `monitoring/alerts.yml`:

| Алерт | Severity | Условие |
|-------|----------|---------|
| `ServiceDown` | critical | Сервис недоступен > 1 мин |
| `HighAlarmRate` | warning | > 0.5 алертов/сек за 5 мин |
| `NoMeasurements` | warning | Нет измерений > 3 мин |
| `HighAPILatency` | warning | p95 API > 1 сек за 3 мин |

## 🚀 Эксплуатация

### Runbook

Инструкция для on-call инженера: диагностика алертов, типовые операции, восстановление после сбоев — в **[docs/RUNBOOK.md](docs/RUNBOOK.md)**.

### SLO / SLI

| Метрика | SLI | SLO |
|---------|-----|-----|
| Доступность Web UI | `up{job="opc-monitor"}` | ≥ 99% в месяц |
| Доступность OPC Client | `up{job="opc-client"}` | ≥ 99% в месяц |
| Латентность API (p95) | `histogram_quantile(0.95, api_latency_seconds_bucket)` | < 500 ms |
| Задержка сбора данных | `rate(opc_values[5m])` | > 0 |
| RTO | — | ≤ 5 минут (helm rollback) |
| RPO | — | ≤ 24 часа (pg_dump) |

**Error Budget:** 1% недоступности в месяц = ~7.2 часа.

### Типовые операции

```bash
# Проверить статус
kubectl get pods -n opc-monitor
kubectl get pvc -n opc-monitor

# Перезапустить сервис (замени <service> на web, client, server, grafana, prometheus, alertmanager, loki, jaeger)
kubectl rollout restart deployment/web -n opc-monitor

# Откатить релиз
helm rollback opc-monitor -n opc-monitor

# Посмотреть логи
kubectl logs -n opc-monitor deployment/web --tail=100
```

Полный список — в **[docs/RUNBOOK.md](docs/RUNBOOK.md)**.

## 🔐 Безопасность

Полный отчёт аудита и список принятых рисков — в **[SECURITY.md](SECURITY.md)**.

### Уровень приложения

- ✅ **JWT-аутентификация** — flask-jwt-extended, HS256, access-token 60 мин
- ✅ **Timing-safe сравнение паролей** — `secrets.compare_digest`
- ✅ **Rate limiting** — Redis-based, `/health` и `/metrics` исключены из лимитов
- ✅ **Security Headers** — Flask-Talisman (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, COOP, COEP, Permissions-Policy)
- ✅ **Локальные библиотеки** — Chart.js, Socket.IO, XLSX, jwt-decode вынесены из CDN в `static/js/`
- ✅ **Параметризованные SQL-запросы** — SQLAlchemy ORM

### Уровень контейнера и Kubernetes

- ✅ **Non-root user** — `USER 1000:1000`, числовой UID
- ✅ **securityContext** — `runAsNonRoot`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`
- ✅ **readOnlyRootFilesystem** для web, client, server + emptyDir для `/tmp`
- ✅ **NetworkPolicy** — default-deny ingress, разрешён только internal + web:5000
- ✅ **PodDisruptionBudget** — minAvailable: 1 для web
- ✅ **ServiceAccount** `opc-app` с `automountServiceAccountToken: false`
- ✅ **initContainer** `wait-for-postgres` — устраняет race condition при рестарте
- ✅ **Resource limits** — CPU, memory, ephemeral-storage для всех контейнеров

### Уровень БД

- ✅ **opc_user — NOT superuser** (NOSUPERUSER NOCREATEROLE NOCREATEDB)
- ✅ **Минимальные привилегии** — CRUD без TRUNCATE/REFERENCES/TRIGGER
- ✅ **init-скрипт** понижает права при первичной инициализации

### Уровень CI/CD

- ✅ **Bandit** — SAST, 0 находок
- ✅ **pip-audit** — SCA, 0 CVE
- ✅ **Semgrep** — SAST (p/python, p/flask, p/owasp-top-ten)
- ✅ **Trivy** — образ: 0 CVE; Terraform config scan
- ✅ **Hadolint** — Dockerfile: 0 WARN
- ✅ **Checkov** — Kubernetes, Helm, Terraform
- ✅ **kube-score** / **kubesec** — анализ манифестов
- ✅ **Dependabot** — обновление зависимостей и SHA-пины actions

### Соответствие стандартам

- ✅ **OWASP Top 10** — A01, A02, A03, A05, A07
- ✅ **CIS Docker Benchmark** — non-root user, healthcheck
- ✅ **CIS Kubernetes Benchmark** — securityContext, resource limits, NetworkPolicy

### Известные ограничения

- Симулятор PLC не использует TLS/шифрование OPC UA — допустимо для демонстрации.
- Alertmanager использует receiver `default` (логирует в stdout); Telegram-интеграция требует bot_token.
- CSP содержит `script-src 'self' 'unsafe-inline'` — UI использует inline-обработчики; вынос в `static/js/app.js` запланирован.

## 🔑 Управление секретами

### Для Helm-деплоя (прод)

Секреты хранятся в **`helm/opc-monitor/values-secrets.yaml`** — файл в `.gitignore`, не попадает в репозиторий.

```bash
cp helm/opc-monitor/values-secrets.yaml.example helm/opc-monitor/values-secrets.yaml
# Заполнить реальными значениями:
#   jwtSecretKey     — python -c "import secrets; print(secrets.token_hex(32))"
#   postgresPassword — пароль БД
#   adminPassword    — пароль admin в web UI
#   grafanaPassword  — пароль Grafana
```

Деплой:

```bash
helm upgrade --install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --values ./helm/opc-monitor/values-prod.yaml \
  --values ./helm/opc-monitor/values-secrets.yaml
```

### Для CI/CD (GitHub Actions)

Секреты хранятся в **GitHub Secrets** и пробрасываются в `cd.yml`:

| Secret | Назначение |
|--------|-----------|
| `JWT_SECRET_KEY` | Подпись JWT-токенов (64 hex) |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL |
| `ADMIN_PASSWORD` | Пароль admin в web UI |
| `GRAFANA_PASSWORD` | Пароль Grafana |

Настроить: **Settings → Secrets and variables → Actions → New repository secret**.

### Для локальной разработки

Через `.env` (см. `.env.example`) для Docker Compose.

### Что НЕ должно попадать в репо

- `helm/opc-monitor/values-secrets.yaml` — в `.gitignore`
- `.env`, `.env.*` — в `.gitignore`
- `terraform/terraform.tfvars` — в `.gitignore`
- `security-audit/` — в `.gitignore` (локальные отчёты сканеров)

### Продакшен-подходы

| Инструмент | Как работает |
|------------|--------------|
| **External Secrets Operator** | Синхронизирует секреты из Vault / Yandex Lockbox / AWS Secrets Manager |
| **Sealed Secrets** | Секреты шифруются публичным ключом и коммитятся в Git |
| **SOPS + age/KMS** | Шифрование файлов values; расшифровка при деплое |
| **HashiCorp Vault + Agent Injector** | Секреты инжектятся в поды напрямую из Vault |

## 🧪 Тестирование

```bash
pip install -r requirements.txt
pytest tests/ -v
pytest tests/ -v --cov=. --cov-report=term-missing
```

**41 тест** покрывают:

### Unit-тесты (`tests/test_utils.py`)
- `get_param_status` — двусторонний и односторонний контроль, edge cases
- `parse_datetime` — 5 сценариев парсинга
- Конвертеры температуры и давления
- Лейблы единиц измерения

### Integration-тесты (`tests/test_api.py`)
- Healthcheck (`/health`)
- Авторизация (`/api/auth/login`) — успех и провал
- JWT-защита (`/api/latest`, `/api/history`, `/api/params`)
- Metrics (`/metrics`)
- Root (`/`)

## 📁 Структура проекта

```
opc-monitor/
├── .github/workflows/           # CI/CD
│   ├── ci.yml                   # tests + build + Trivy + push
│   └── cd.yml                   # deploy через Helm
├── .github/dependabot.yml       # auto-update deps + SHA-pins
├── argocd/
│   └── application.yaml         # ArgoCD Application (GitOps)
├── helm/opc-monitor/            # Helm-чарт
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-staging.yaml
│   ├── values-prod.yaml
│   ├── values-secrets.yaml.example
│   ├── dashboards/
│   │   └── opc-monitor.json
│   └── templates/
├── k8s/                         # Kubernetes-манифесты (kubectl)
├── monitoring/
│   ├── prometheus.yml
│   ├── alerts.yml               # правила алертов
│   ├── alertmanager.yml
│   ├── loki-config.yml          # конфиг Loki
│   ├── promtail-config.yml      # конфиг Promtail
│   ├── grafana-datasources.yml  # provisioning datasources
│   ├── grafana-dashboards.yml
│   └── grafana-dashboard.json
├── terraform/                   # IaC для Yandex Cloud
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_utils.py
│   └── test_api.py
├── docs/
│   ├── RUNBOOK.md
│   └── screenshots/
├── static/js/                   # локальные библиотеки (были в CDN)
│   ├── app.js
│   ├── chart.umd.min.js
│   ├── jwt-decode.min.js
│   ├── socket.io.min.js
│   └── xlsx.full.min.js
├── templates/index.html
├── client.py                    # OPC UA клиент
├── server.py                    # OPC UA симулятор (PLCSimulator)
├── web_app.py                   # Flask приложение
├── db.py                        # SQLAlchemy + Redis
├── tracing.py                   # OpenTelemetry инициализация
├── utils.py
├── config.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .bandit                      # конфиг Bandit
├── SECURITY.md                  # отчёт аудита и принятые риски
└── README.md
```

## 🌩️ Infrastructure as Code (Terraform)

Полная Terraform-конфигурация для развёртывания в Yandex Cloud:

| Ресурс | Описание |
|--------|----------|
| **VPC Network** | Сеть с публичной и приватными подсетями |
| **NAT Gateway** | Интернет-доступ для приватных подсетей |
| **Security Group** | Правила firewall: SSH по IP владельца, k3s API/VXLAN/kubelet — internal |
| **k3s Master** | VM с k3s control-plane |
| **k3s Workers ×2** | VM с k3s агентами в разных зонах |
| **Managed PostgreSQL** | Кластер БД (s2.micro, 20 GB SSD) |

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform validate && terraform plan
terraform apply     # создаст платные ресурсы
terraform destroy   # удалит
```

## 📊 API Endpoints

| Метод | Endpoint | Описание | Rate Limit |
|-------|----------|----------|------------|
| `POST` | `/api/auth/login` | Получить JWT-токен | 5/min |
| `POST` | `/api/auth/refresh` | Обновить токен | 200/min |
| `GET` | `/api/params` | Список параметров | 200/min |
| `GET` | `/api/latest` | Последнее измерение | 200/min |
| `GET` | `/api/history` | История измерений | 200/min |
| `GET` | `/api/alarms` | История аварий | 200/min |
| `GET` | `/api/stats` | Статистика | 200/min |
| `GET` | `/api/thresholds` | Текущие пороги | 200/min |
| `POST` | `/api/thresholds/update` | Обновить пороги | 200/min |
| `GET` | `/api/export` | Экспорт данных (CSV) | 200/min |
| `GET` | `/health` | Health check | — |
| `GET` | `/metrics` | Prometheus метрики | — |

Полная документация: http://localhost:5000/api/docs

## 📝 Лицензия

MIT. См. [LICENSE](LICENSE).

## 👤 Автор

**Rosimus**

- GitHub: [@Rosimus](https://github.com/Rosimus)
- Email: rosimus854@gmail.com

---

⭐ Если проект был полезен — поставьте звезду!