# Security Policy

## Уровень приложения

- **JWT-аутентификация** — flask-jwt-extended, HS256, access-token 60 мин
- **Timing-safe сравнение паролей** — `secrets.compare_digest`
- **Rate limiting** — Redis-based, `/health` и `/metrics` исключены из лимитов
- **Security headers** — Flask-Talisman (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, COOP, COEP, Permissions-Policy)
- **Non-root** контейнеры, k8s securityContext (`runAsNonRoot`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`)
- **readOnlyRootFilesystem** для web, client, server
- **Локальные библиотеки** — Chart.js, Socket.IO, XLSX, jwt-decode вынесены из CDN в `static/js/`

## Уровень БД (PostgreSQL 15)

### Роли и привилегии

Приложение подключается как `opc_user` — **NOT superuser, NOT createrole, NOT createdb**.
Привилегии на таблицы: `INSERT, SELECT, UPDATE, DELETE` (без `TRUNCATE`, `REFERENCES`, `TRIGGER`).

Понижение привилегий выполняется init-скриптом (`postgres-init` ConfigMap) при первичной инициализации БД и вручную применено к существующему инстансу.

### RLS — принятый риск

Row-Level Security не внедрён — приложение single-tenant, один клиент БД. При переходе к multi-tenant потребуется разделение ролей (`opc_migrator` / `opc_app`) и RLS-политики с `current_setting('app.tenant_id')`.

## Уровень Kubernetes

- **NetworkPolicy** — default-deny на ingress, разрешён internal traffic + web:5000
- **PodDisruptionBudget** — minAvailable: 1 для web
- **ServiceAccount** `opc-app` с `automountServiceAccountToken: false`
- **initContainer** `wait-for-postgres` — устраняет race condition при перезапуске postgres
- **resource limits/requests** — CPU, memory, ephemeral-storage для всех контейнеров
- **readOnlyRootFilesystem + emptyDir /tmp** — для web, client, server

## Уровень инфраструктуры (Terraform, Yandex Cloud)

- **VPC Network** — публичная подсеть для master, приватные для workers
- **NAT Gateway** — интернет для приватных подсетей через egress
- **Security Group:**
  - SSH (22) — whitelist по IP владельца (`/32`)
  - k3s API (6443), VXLAN (8472), kubelet (10250) — только internal `10.10.0.0/16`
  - HTTP/HTTPS (80/443) — публично (веб-приложение)
  - Grafana (3000) — только internal `10.10.0.0/16`
- **Managed PostgreSQL** — TLS обязателен, публичный доступ выключен
- **k3s cluster** — 1 master + 2 workers в разных зонах

## Уровень CI/CD

- **Bandit** — SAST, 0 находок
- **pip-audit** — SCA, 0 CVE
- **Semgrep** — SAST (p/python, p/flask, p/owasp-top-ten)
- **Trivy** — образ: 0 CVE; Terraform: config scan
- **Hadolint** — Dockerfile: 0 WARN
- **kube-score** / **kubesec** — анализ манифестов
- **Checkov** — Kubernetes, Helm, Terraform
- **Dependabot** — обновление зависимостей и SHA-пины GitHub Actions

## Аудит (текущий статус)

| Этап | Инструмент | Результат |
|------|------------|-----------|
| SAST | Bandit | 0 находок |
| SCA | pip-audit | 0 CVE |
| SAST | Semgrep | 10 WARN (workflows, закроет Dependabot) |
| JWT | jwt_tool (alg:none) | Устойчив — все подделки отклонены (422) |
| API | OWASP ZAP | 0 FAIL, 4 WARN (все не-уязвимости) |
| БД | SQL-аудит RLS/ролей | Суперюзер понижен, RLS не требуется |
| K8s/Docker | Trivy image | 0 CVE |
| K8s/Docker | Hadolint | 0 WARN |
| K8s | kube-score | ~24 CRITICAL (приняты) |
| K8s | kubesec | 9/10 (web), 7/10 (client, server) |
| K8s | Checkov | 956 Passed / 47 Failed (приняты) |
| Terraform | Checkov | 11 Passed / 1 Failed (принят) |
| Terraform | Trivy config | 0 находок |

## Принятые риски (осознанные компромиссы)

| ID | Категория | Обоснование |
|----|-----------|-------------|
| CKV_K8S_15 | ImagePullPolicy: Always | В local minikube `IfNotPresent` правильнее; CD использует уникальные sha-теги |
| CKV_K8S_43 | Image должен использовать digest | Тег подставляется CI через `--set image.tag=sha-<commit>` |
| CKV_K8S_40 | UID > 10000 | UID 1000 — стандарт Debian; смена требует пересборки образа + потери данных в PVC |
| CKV_K8S_35 | Secrets как файлы вместо env | Env проще и достаточно для single-tenant; секреты не хардкодятся |
| CKV_K8S_22 | readOnlyRootFilesystem для stateful | Postgres, Redis, Grafana, Prometheus, Loki, Jaeger, Alertmanager пишут в /var, /etc, /data |
| CKV_K8S_23 | Promtail как root | Читает /var/log/containers/*.log — симлинки, принадлежащие root |
| CKV_YC_2 | Public IP на k3s_master | Для управления k3s извне; в проде — bastion + private network. SG ограничивает SSH/API по IP |
| kube-score | Same liveness/readiness probe | Оба probe на `/health`, для stateless-приложения корректно |
| ZAP | CSP `script-src 'unsafe-inline'` | UI использует inline-обработчики (`onclick`, `onchange`) |
| ZAP | Non-Storable Content | False positive — ZAP ругается в обе стороны |
| pip-audit | opcua 0.98.13 (CVE) | Фикса нет, риск принят; DoS требует доступа к OPC UA порту |

## Известные ограничения

- OPC UA симулятор работает без TLS — допустимо для демонстрации.
- Socket.IO клиент в браузере не подключён к серверу (real-time данные через polling).
- Alertmanager использует receiver `default` (логи в stdout); Telegram-интеграция требует bot_token.

## Как сообщить об уязвимости

Открыть issue с префиксом `[SECURITY]` или написать на rosimus854@gmail.com.
