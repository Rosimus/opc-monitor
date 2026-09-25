# OPC Monitor

[![CI](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/ci.yml)
[![CD](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml/badge.svg)](https://github.com/Rosimus/opc-monitor/actions/workflows/cd.yml)
[![Container Registry](https://img.shields.io/badge/registry-ghcr.io-blue)](https://github.com/Rosimus/opc-monitor/pkgs/container/opc-monitor)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-k3s%20%7C%20minikube-326CE5)](https://kubernetes.io/)
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
- 🔄 **CI/CD** через GitHub Actions с self-hosted runner

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
| **Оркестрация** | Kubernetes (k3s / Minikube), Helm |
| **CI/CD** | GitHub Actions, GHCR, self-hosted runner |
| **Мониторинг** | Prometheus, Grafana |
| **Контейнеризация** | Docker, Docker Compose |
| **IaC** | Terraform (Yandex Cloud) |

## 🚀 Быстрый старт

### Предварительные требования

- **Windows 10/11** с WSL2 (или Linux/macOS)
- **Docker Desktop** 4.20+
- **Minikube** 1.30+
- **kubectl** 1.27+
- **Helm** 3.12+ (опционально)

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

### Запуск в Kubernetes (Minikube)

```bash
# 1. Запустить Minikube
minikube start --driver=docker --memory=4096 --cpus=4

# 2. Собрать образ
docker build -t opc-monitor:latest .

# 3. Загрузить в Minikube
minikube image load opc-monitor:latest

# 4. Применить манифесты
kubectl apply -f k8s/

# 5. Проброс порта
kubectl port-forward -n opc-monitor service/web 5000:5000
```

**Доступ**: http://localhost:5000

### Деплой через Helm (рекомендуется)

```bash
helm upgrade --install opc-monitor ./helm/opc-monitor \
  --namespace opc-monitor \
  --create-namespace \
  --values ./helm/opc-monitor/values-prod.yaml \
  --wait
```

## 🔄 CI/CD Pipeline

Проект использует **полностью автоматизированный CI/CD** через GitHub Actions:

### CI — Build & Push

При каждом push в `main`:
1. ✅ Автоматическая сборка Docker-образа
2. ✅ Загрузка в GitHub Container Registry (GHCR)
3. ✅ Теги: `latest`, `sha-<commit>`, `<branch>`

### CD — Deploy to Minikube

После успешного CI:
1. ✅ Self-hosted runner получает задачу
2. ✅ Скачивает образ из GHCR
3. ✅ Загружает в Minikube
4. ✅ Обновляет деплойменты (rolling update)
5. ✅ Проверяет статус

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

## 📁 Структура проекта

```
opc-monitor/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml               # CI: сборка + push образа
│   │   └── cd.yml               # CD: деплой в Minikube
│   └── dependabot.yml           # Автообновление зависимостей
├── helm/
│   └── opc-monitor/             # Helm-чарт
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-prod.yaml
│       └── templates/           # Kubernetes-шаблоны
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
│   ├── main.tf
│   ├── network.tf
│   ├── k3s.tf
│   ├── database.tf
│   └── ...
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

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/auth/login` | Получить JWT-токен |
| `POST` | `/api/auth/refresh` | Обновить токен |
| `GET` | `/api/params` | Список параметров |
| `GET` | `/api/latest` | Последнее измерение |
| `GET` | `/api/history` | История измерений |
| `GET` | `/api/alarms` | История аварий |
| `GET` | `/api/stats` | Статистика |
| `GET` | `/api/thresholds` | Текущие пороги |
| `POST` | `/api/thresholds/update` | Обновить пороги |
| `GET` | `/api/export` | Экспорт данных (CSV) |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus метрики |

Полная документация: http://localhost:5000/api/docs

## 🔐 Безопасность

- ✅ **JWT-аутентификация** для API
- ✅ **Kubernetes Secrets** для хранения паролей (не в Git)
- ✅ **`.gitignore`** исключает секреты
- ✅ **HTTPS** через Ingress + cert-manager (при деплое в облако)
- ✅ **Dependabot** автоматически обновляет зависимости
- ✅ **Security Groups** в облаке ограничивают доступ

## 📸 Скриншоты

> _Добавьте сюда скриншоты вашего дашборда и Grafana_
>
> ```
> docs/screenshots/dashboard.png
> docs/screenshots/alerts.png
> docs/screenshots/grafana.png
> ```

## 🧪 Тестирование

```bash
# Запустить приложение локально
python web_app.py

# API тесты
curl http://localhost:5000/health
curl -H "Authorization: Bearer <TOKEN>" http://localhost:5000/api/latest
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
- [Chart.js](https://www.chartjs.org/)
- [Kubernetes](https://kubernetes.io/)

---

⭐ Если проект был полезен — поставьте звезду!