# OPC Monitor

[![CI](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml)
[![CD](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml)
[![Container Registry](https://img.shields.io/badge/registry-ghcr.io-blue)](https://github.com/Rosimus/opc-monitor/pkgs/container/opc-monitor)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-k3s%20%7C%20minikube-326CE5)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/helm-3.12+-0F1689)](https://helm.sh/)
[![Tests](https://img.shields.io/badge/tests-29%20passed-brightgreen)](#-тестирование)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Система мониторинга промышленного оборудования на OPC UA с веб-интерфейсом, алертами, аналитикой и полным CI/CD pipeline.

## ✨ Возможности

- 📊 **Real-time мониторинг** 8 параметров (температура, давление, влажность, вибрация, ток, скорость, уровень, частота)
- 🎬 **Реалистичный симулятор PLC** — random walk, mean reversion, суточные колебания, случайные и каскадные аварии
- 🚨 **Многоуровневые алерты** (Warning / Alarm) с Email и Telegram уведомлениями
- 📈 **Графики в реальном времени** — Chart.js с пороговыми линиями
- 🔐 **JWT-аутентификация** веб-интерфейса
- 📥 **Экспорт данных** в CSV и Excel
- 🎯 **REST API** с автогенерируемой документацией (Swagger)
- 📉 **Метрики Prometheus** + **Grafana dashboard as code** (5 панелей, provisioning через ConfigMap)
- 🐳 **Docker-образ** с автоматической сборкой
- ☸️ **Kubernetes-деплой** через kubectl / Helm
- ⛵ **Helm-чарт** с параметризацией под staging и prod
- 🌩️ **Terraform** — IaC для Yandex Cloud (k3s, managed PostgreSQL)
- 🔄 **CI/CD** через GitHub Actions с self-hosted runner
- ✅ **29 pytest-тестов** в CI pipeline
- 📦 **GHCR** — автоматическая загрузка образов
- 🛡️ **Security Hardened** — non-root, security headers, rate limiting, Trivy scan

## 🏗️ Архитектура

Проект — это **распределённая система из 7 контейнеров**, объединённых общей сетью и слоем хранения. Каждый сервис выполняет одну функцию; взаимодействие идёт через базу данных, Redis-кэш и HTTP-протоколы.

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
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│           Prometheus + Grafana                           │
│           Мониторинг всей системы (provisioned)          │
└──────────────────────────────────────────────────────────┘
```

## 🛠️ Стек технологий

| Категория | Технологии |
|-----------|------------|
| **Backend** | Python 3.11, Flask, SQLAlchemy, Gunicorn, structlog |
| **Frontend** | Vanilla JS, Chart.js, Socket.IO client |
| **База данных** | PostgreSQL 15, Redis 7 (кэш) |
| **Аутентификация** | JWT (flask-jwt-extended) |
| **Безопасность** | Flask-Talisman, Flask-Limiter, Trivy |
| **Оркестрация** | Kubernetes (k3s / Minikube), Helm 3 |
| **CI/CD** | GitHub Actions, GHCR, self-hosted runner |
| **Мониторинг** | Prometheus, Grafana (provisioning as code) |
| **Контейнеризация** | Docker, Docker Compose |
| **IaC** | Terraform (Yandex Cloud) |
| **Тесты** | pytest, pytest-cov |

## 📸 Скриншоты

### 📊 Real-time Dashboard

![Dashboard](docs/screenshots/dashboard.png)

*Real-time мониторинг 8 параметров с карточками статусов, графиками и пороговыми линиями*

### 🚨 История аварий

![Alerts](docs/screenshots/alerts.png)

*Полная история аварий с фильтрацией по времени, параметрам и статусу*

### 📈 Grafana Dashboard

![Grafana](docs/screenshots/grafana.png)

*Provisioned дашборд с 5 панелями: значения параметров, статус системы, алерты, RPS и латентность API*

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
# 1. Клонировать репозиторий
git clone https://github.com/Rosimus/opc-monitor.git
cd opc-monitor

# 2. Создать .env из примера
copy .env.example .env
# Отредактировать .env (пароли, настройки)

# 3. Запустить
docker-compose up -d
```

**Доступ**: http://localhost:5000

### Запуск в Kubernetes через Helm (рекомендуется)

```bash
# 1. Запустить Minikube
minikube start --driver=docker --memory=4096 --cpus=4

# 2. Собрать образ
docker build -t opc-monitor:latest .
minikube image load opc-monitor:latest

# 3. Установить через Helm
helm install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --create-namespace \
  --values ./helm/opc-monitor/values-prod.yaml

# 4. Проброс портов
kubectl port-forward -n opc-monitor service/web 5000:5000
kubectl port-forward -n opc-monitor service/grafana 3000:3000
```

**Доступ**:
- Web UI: http://localhost:5000
- Grafana: http://localhost:3000 (admin / admin)

## 🔄 CI/CD Pipeline

Проект использует **полностью автоматизированный CI/CD** через GitHub Actions.

### CI — Test, Build & Push

При каждом push в `main`:
1. ✅ **Run Tests** — 29 pytest-тестов + coverage report
2. ✅ Автоматическая сборка Docker-образа
3. ✅ Загрузка в GitHub Container Registry (GHCR)
4. ✅ **Trivy scan** — проверка на уязвимости (CRITICAL/HIGH)
5. ✅ Теги: `latest`, `sha-<commit>`, `<branch>`

### CD — Deploy to Minikube

После успешного CI:
1. ✅ Self-hosted runner получает задачу
2. ✅ Скачивает образ из GHCR
3. ✅ Загружает в Minikube
4. ✅ Выполняет `helm upgrade --install` (атомарно)
5. ✅ Проверяет готовность через `kubectl rollout status`
6. ✅ Публикует summary с состоянием подов

**Время от `git push` до работающего приложения: ~60 секунд** ⚡

### Откат

```bash
helm history opc-monitor -n opc-monitor
helm rollback opc-monitor -n opc-monitor
```

## 🔐 Безопасность

### Уровень приложения
- ✅ **JWT-аутентификация** — flask-jwt-extended
- ✅ **Rate limiting** — защита от брутфорса (5 попыток/мин на login)
- ✅ **Security Headers** — Flask-Talisman (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- ✅ **Non-root user** в Docker
- ✅ **Параметризованные SQL-запросы** — SQLAlchemy ORM

### Уровень CI/CD
- ✅ **Trivy** — сканирование образа на уязвимости (CRITICAL/HIGH)
- ✅ **GitHub Secrets** для чувствительных данных
- ✅ **GITHUB_TOKEN** с минимальными правами
- ✅ **pytest + coverage** — тесты как часть pipeline

### Уровень инфраструктуры
- ✅ **securityContext fsGroup: 472** для Grafana
- ✅ **Kubernetes Secrets** для хранения паролей
- ✅ **Security Groups** в Yandex Cloud

### Соответствие стандартам
- ✅ **OWASP Top 10** — A01, A02, A03, A05, A07
- ✅ **CIS Docker Benchmark** — non-root user, healthcheck

### Известные ограничения (для пет-проекта)

- Симулятор PLC не использует TLS/шифрование OPC UA — это допустимо для демонстрации. В продакшене требуется настроить сертификаты и security policy.
- Секреты в Helm values хранятся в открытом виде для упрощения. В продакшене используется External Secrets Operator, SOPS или Yandex Lockbox.
- В CI используется файловый Trivy scan. Образ не сканируется — это можно добавить при необходимости.

## 🧪 Тестирование

```bash
pip install -r requirements.txt
pytest tests/ -v
pytest tests/ -v --cov=. --cov-report=term-missing
```

**29 тестов** покрывают:
- `get_param_status` — двусторонний и односторонний контроль, edge cases
- `parse_datetime` — 5 сценариев парсинга
- Конвертеры температуры и давления
- Лейблы единиц измерения

## 📁 Структура проекта

```
opc-monitor/
├── .github/workflows/           # CI/CD
│   ├── ci.yml                   # tests + build + Trivy + push
│   └── cd.yml                   # deploy через Helm
├── helm/opc-monitor/            # Helm-чарт
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-staging.yaml
│   ├── values-prod.yaml
│   ├── dashboards/
│   │   └── opc-monitor.json
│   └── templates/
├── k8s/                         # Kubernetes-манифесты (kubectl)
├── monitoring/
│   ├── prometheus.yml
│   ├── grafana-datasources.yml
│   ├── grafana-dashboards.yml
│   └── grafana-dashboard.json
├── terraform/                   # IaC для Yandex Cloud
├── tests/
│   ├── __init__.py
│   └── test_utils.py
├── docs/screenshots/
├── templates/index.html
├── client.py                    # OPC UA клиент
├── server.py                    # OPC UA симулятор (PLCSimulator)
├── web_app.py                   # Flask приложение
├── db.py                        # SQLAlchemy + Redis
├── utils.py
├── config.yaml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md
```

## 🌩️ Infrastructure as Code (Terraform)

Полная Terraform-конфигурация для развёртывания в Yandex Cloud:

| Ресурс | Описание |
|--------|----------|
| **VPC Network** | Сеть с публичной и приватными подсетями |
| **NAT Gateway** | Интернет-доступ для приватных подсетей |
| **Security Group** | Правила firewall для Kubernetes |
| **k3s Master** | VM с k3s control-plane |
| **k3s Workers ×2** | VM с k3s агентами в разных зонах |
| **Managed PostgreSQL** | Кластер БД (s2.micro, 20 GB SSD) |

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Заполнить: yc_token, yc_cloud_id, yc_folder_id, ssh_public_key

terraform init
terraform validate
terraform plan
terraform apply        # создаст платные ресурсы
terraform destroy      # удалит
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