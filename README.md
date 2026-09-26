# OPC Monitor

[![CI](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml)
[![CD](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml)
[![Release](https://img.shields.io/github/v/release/Rosimus/opc-monitor)](https://github.com/Rosimus/opc-monitor/releases)
[![Container Registry](https://img.shields.io/badge/registry-ghcr.io-blue)](https://github.com/Rosimus/opc-monitor/pkgs/container/opc-monitor)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-k3s%20%7C%20minikube-326CE5)](https://kubernetes.io/)
[![Helm](https://img.shields.io/badge/helm-3.12+-0F1689)](https://helm.sh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Система мониторинга OPC UA серверов с веб-интерфейсом, алертами, аналитикой и полным CI/CD pipeline.

## ✨ Возможности

- 📊 **Real-time мониторинг** 8 параметров (температура, давление, влажность, вибрация, ток, скорость, уровень, частота)
- 🚨 **Многоуровневые алерты** (Warning / Alarm) с Email и Telegram уведомлениями
- 📈 **Графики в реальном времени** — Chart.js с пороговыми линиями
- 🔐 **JWT-аутентификация** веб-интерфейса
- 📥 **Экспорт данных** в CSV и Excel
- 🎯 **REST API** с автогенерируемой документацией (Swagger)
- 📉 **Метрики Prometheus** + готовый dashboard в Grafana
- 🐳 **Docker-образ** с автоматической сборкой
- ☸️ **Kubernetes-деплой** через kubectl / Helm
- ⛵ **Helm-чарт** с параметризацией для multi-environment
- 🔄 **CI/CD** через GitHub Actions с self-hosted runner
- 📦 **GHCR** — автоматическая загрузка образов
- 🛡️ **Security Hardened** — non-root, security headers, rate limiting, Trivy scan

## 🏗️ Архитектура

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
                            │ SQLAlchemy
                            ▼
┌──────────────────────────────────────────────────────────┐
│                PostgreSQL 15                             │
│                measurements, alarms, thresholds          │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│         Web App (Flask + Gunicorn)                       │
│  • REST API с JWT-аутентификацией                        │
│  • Web UI (Chart.js, dark/light тема)                    │
│  • Security headers (Talisman) + Rate limiting           │
│  • Метрики Prometheus на :5000/metrics                   │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│           Prometheus + Grafana                           │
│           Мониторинг всей системы                        │
└──────────────────────────────────────────────────────────┘
```

## 🛠️ Стек технологий

| Категория | Технологии |
|-----------|------------|
| **Backend** | Python 3.11, Flask, SQLAlchemy, Gunicorn, structlog |
| **Frontend** | Vanilla JS, Chart.js, Socket.IO client |
| **База данных** | PostgreSQL 15, Redis |
| **Аутентификация** | JWT (flask-jwt-extended) |
| **Безопасность** | Flask-Talisman, Flask-Limiter, Trivy |
| **Оркестрация** | Kubernetes (k3s / Minikube), Helm 3 |
| **CI/CD** | GitHub Actions, GHCR, self-hosted runner |
| **Мониторинг** | Prometheus, Grafana |
| **Контейнеризация** | Docker, Docker Compose |
| **IaC** | Terraform (Yandex Cloud — готовая конфигурация) |

## 📸 Скриншоты

### 📊 Real-time Dashboard

![Dashboard](docs/screenshots/dashboard.png)

*Real-time мониторинг 8 параметров с карточками статусов, графиками и пороговыми линиями*

### 🚨 История аварий

![Alerts](docs/screenshots/alerts.png)

*Полная история аварий с фильтрацией по времени, параметрам и статусу*

### 📈 Grafana Dashboard

![Grafana](docs/screenshots/grafana.png)

*Метрики Prometheus: значения всех параметров, статус системы, счётчик алертов*

### ✅ CI/CD Pipeline

![Actions](docs/screenshots/actions.png)

*18 workflow runs — история настройки и работы CI/CD. Время от `git push` до деплоя: ~60 секунд*

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

# 3. Загрузить в Minikube
minikube image load opc-monitor:latest

# 4. Установить через Helm
helm install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --create-namespace \
  --values ./helm/opc-monitor/values-prod.yaml

# 5. Проброс порта
kubectl port-forward -n opc-monitor service/web 5000:5000
```

**Доступ**: http://localhost:5000

### Запуск в Kubernetes через kubectl (классический способ)

```bash
kubectl apply -f k8s/
kubectl port-forward -n opc-monitor service/web 5000:5000
```

## 🔄 CI/CD Pipeline

Проект использует **полностью автоматизированный CI/CD** через GitHub Actions:

### CI — Build & Push

При каждом push в `main`:
1. ✅ Автоматическая сборка Docker-образа
2. ✅ Загрузка в GitHub Container Registry (GHCR)
3. ✅ **Trivy scan** — проверка на уязвимости (CRITICAL/HIGH)
4. ✅ Теги: `latest`, `sha-<commit>`, `<branch>`

### CD — Deploy to Minikube

После успешного CI:
1. ✅ Self-hosted runner получает задачу
2. ✅ Скачивает образ из GHCR
3. ✅ Загружает в Minikube
4. ✅ Выполняет `helm upgrade --install` (атомарно)
5. ✅ Проверяет готовность через `kubectl rollout status`
6. ✅ Публикует summary с состоянием подов

**Время от `git push` до работающего приложения: ~60 секунд** ⚡

### Как использовать

```bash
# Просто внесите изменения и запушьте:
git add .
git commit -m "Your changes"
git push

# Дальше — всё автоматически!
# Смотрите прогресс: https://github.com/Rosimus/opc-monitor/actions
```

### Откат

```bash
# Посмотреть историю релизов
helm history opc-monitor -n opc-monitor

# Откатиться на предыдущую ревизию
helm rollback opc-monitor -n opc-monitor
```

## 🔐 Безопасность

### Уровень приложения
- ✅ **JWT-аутентификация** — flask-jwt-extended
- ✅ **Rate limiting** — защита от брутфорса (5 попыток/мин на login)
- ✅ **Security Headers** — Flask-Talisman:
  - `Content-Security-Policy` — защита от XSS
  - `X-Frame-Options: DENY` — защита от Clickjacking
  - `Strict-Transport-Security` — форсирование HTTPS (1 год)
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- ✅ **Non-root user** в Docker (`appuser`)
- ✅ **Параметризованные SQL-запросы** — SQLAlchemy ORM

### Уровень CI/CD
- ✅ **Trivy** — сканирование образа на уязвимости (CRITICAL/HIGH)
- ✅ **GitHub Secrets** для чувствительных данных
- ✅ **GITHUB_TOKEN** с минимальными правами
- ✅ **Отчёт Trivy** сохраняется как artifact

### Уровень инфраструктуры
- ✅ **Kubernetes Secrets** для хранения паролей
- ✅ **`.gitignore`** исключает секреты
- ✅ **Security Groups** в Yandex Cloud
- ✅ **Отдельные сетевые подсети** (public/private)

### Соответствие стандартам
- ✅ **OWASP Top 10** — покрыты: A01 (Access Control), A02 (Crypto), A03 (Injection), A05 (Misconfiguration), A07 (Auth Failures)
- ✅ **CIS Docker Benchmark** — non-root user, healthcheck

### Рекомендации для продакшена
- 🔲 External Secrets Operator (Yandex Lockbox)
- 🔲 Network Policies между подами
- 🔲 PodSecurityPolicy
- 🔲 Secrets rotation каждые 90 дней
- 🔲 WAF (Cloudflare / Yandex Smart Web Security)

## 📁 Структура проекта

```
opc-monitor/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # CI: сборка + Trivy scan + push образа
│   │   └── cd.yml               # CD: деплой через Helm
│   └── dependabot.yml           # Автообновление зависимостей
├── helm/
│   └── opc-monitor/             # Helm-чарт
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-staging.yaml
│       ├── values-prod.yaml
│       └── templates/           # Kubernetes-шаблоны
│           ├── _helpers.tpl
│           ├── secret.yaml
│           ├── configmap.yaml
│           ├── postgres.yaml
│           ├── redis.yaml
│           ├── server.yaml
│           ├── client.yaml
│           ├── web.yaml
│           ├── prometheus.yaml
│           ├── grafana.yaml
│           ├── ingress.yaml
│           └── hpa.yaml
├── k8s/                         # Kubernetes-манифесты (kubectl)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml.example
│   ├── postgres.yaml
│   ├── redis.yaml
│   ├── server.yaml
│   ├── client.yaml
│   ├── web.yaml
│   ├── prometheus.yaml
│   ├── grafana.yaml
│   └── ...
├── monitoring/
│   ├── prometheus.yml
│   └── grafana-dashboard.json
├── terraform/                   # IaC для Yandex Cloud
│   ├── versions.tf
│   ├── variables.tf
│   ├── main.tf
│   ├── network.tf
│   ├── k3s.tf
│   ├── database.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   └── templates/
│       ├── k3s-master-cloud-init.yaml
│       └── k3s-worker-cloud-init.yaml
├── docs/
│   └── screenshots/             # Скриншоты для README
│       ├── dashboard.png
│       ├── alerts.png
│       ├── grafana.png
│       └── actions.png
├── templates/
│   └── index.html               # Web UI (SPA)
├── scripts/                     # Скрипты автоматизации
│   ├── deploy.ps1
│   ├── minikube-start.ps1
│   └── minikube-start.sh
├── client.py                    # OPC UA клиент
├── server.py                    # OPC UA симулятор
├── web_app.py                   # Flask приложение
├── db.py                        # SQLAlchemy модели + БД
├── utils.py                     # Общие утилиты
├── config.yaml                  # Конфигурация приложения
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
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
| `POST` | `/api/notify` | Уведомление (внутреннее) | 60/min |
| `GET` | `/health` | Health check | — |
| `GET` | `/metrics` | Prometheus метрики | — |

Полная документация: http://localhost:5000/api/docs

## 🌩️ Infrastructure as Code (Terraform)

Проект содержит **полную Terraform-конфигурацию** для развёртывания в Yandex Cloud:

### Что создаётся

| Ресурс | Описание |
|--------|----------|
| **VPC Network** | Сеть с публичной и приватными подсетями |
| **NAT Gateway** | Интернет-доступ для приватных подсетей |
| **Security Group** | Правила firewall для Kubernetes |
| **k3s Master** | VM с k3s control-plane (Ubuntu 22.04) |
| **k3s Workers ×2** | VM с k3s агентами в разных зонах |
| **Managed PostgreSQL** | Кластер БД (s2.micro, 20 GB SSD) |
| **Cert-manager** | Автоматический TLS через Let's Encrypt |

### Стоимость

| Компонент | Цена/мес |
|-----------|----------|
| 3 VM (2 vCPU, 4 GB) | ~6000 ₽ |
| Managed PostgreSQL | ~2500 ₽ |
| Object Storage (tfstate) | ~10 ₽ |
| **Итого** | **~8600 ₽/мес** |

### Использование

```bash
cd terraform

# 1. Скопировать пример
cp terraform.tfvars.example terraform.tfvars

# 2. Заполнить: yc_token, yc_cloud_id, yc_folder_id, ssh_public_key
nano terraform.tfvars

# 3. Инициализация
terraform init

# 4. Проверка синтаксиса
terraform validate

# 5. Посмотреть план (без создания ресурсов)
terraform plan

# 6. Создать инфраструктуру (платно!)
terraform apply

# 7. Удалить всё
terraform destroy
```

> ⚠️ **Внимание:** `terraform apply` создаст платные ресурсы (~8600 ₽/мес). Используйте `terraform destroy` для удаления.

## 🧪 Тестирование

```bash
# Запустить приложение локально
python web_app.py

# Проверить health
curl http://localhost:5000/health

# Проверить security headers
curl -I http://localhost:5000/health

# Проверить rate limiting (6 запросов подряд)
for i in {1..6}; do
  curl -X POST http://localhost:5000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"wrong","password":"wrong"}' \
    -w "Request $i: %{http_code}\n" -o /dev/null
done
```

## 📝 Лицензия

Этот проект распространяется под лицензией **MIT**. См. файл [LICENSE](LICENSE) для деталей.

## 👤 Автор

**Rosimus**

- GitHub: [@Rosimus](https://github.com/Rosimus)
- Email: rosimus854@gmail.com

## 🙏 Благодарности

- [OPC UA Python](https://github.com/FreeOpcUa/python-opcua)
- [Flask](https://flask.palletsprojects.com/)
- [Flask-Talisman](https://github.com/GoogleCloudPlatform/flask-talisman)
- [Flask-Limiter](https://flask-limiter.readthedocs.io/)
- [Chart.js](https://www.chartjs.org/)
- [Kubernetes](https://kubernetes.io/)
- [Helm](https://helm.sh/)
- [Trivy](https://github.com/aquasecurity/trivy)

---

⭐ Если проект был полезен — поставьте звезду!