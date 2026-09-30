# ADR-0004: Self-hosted runner vs GitHub-hosted для CD

- **Статус:** Accepted
- **Дата:** 2026-09
- **Контекст:** выбор runner'а для job'а деплоя в локальный Minikube

## Context

Проект использует CI/CD через GitHub Actions:

- **CI job** (`test` + `build` + `trivy`) — полностью изолирован, работает с исходниками и Docker-образом. Может работать на GitHub-hosted runner.
- **CD job** (`deploy`) — деплоит в **локальный Minikube**, который крутится на моей машине. Нужно:

  - Скачать образ из GHCR
  - Загрузить его в Minikube (`minikube image load`)
  - Обновить Helm-релиз в текущем kube-context
  - Дождаться `rollout status`

GitHub-hosted runner **не может** этого сделать — он виртуальный, у него нет доступа к моему Minikube.

## Decision

**CI работает на GitHub-hosted runner, CD — на self-hosted runner (моя машина).**

Причины:

- **Бесплатно.** Self-hosted runner не тарифицируется минутами GitHub Actions. Для pet-проекта это важно — иначе CD-задача на 50–60 секунд накапливается в биллинг.
- **Прямой доступ к Minikube.** Self-hosted runner выполняется внутри моей сети, видит Docker Desktop и Minikube по localhost.
- **Реалистичный сценарий.** Такой подход часто встречается в enterprise: GitHub-hosted для CI, self-hosted за VPN — для деплоя в internal-кластер.

## Consequences

**Плюсы:**

- CD работает быстро (~50 сек) — образ уже в GHCR, скачивается и заливается в Minikube за секунды.
- Нет необходимости открывать порты Minikube в интернет (self-hosted runner исходящий).
- Реалистичная демонстрация: показать, что умею настраивать runner, описывать его установку в README.

**Минусы и риски:**

- **Секьюрность.** Self-hosted runner выполняется **на моей машине** под моим пользователем. Если кто-то сможет запушить PR с изменённым workflow — теоретически может выполнить произвольный код. **Митигация:** workflow запускается только на события `workflow_run` после CI, и только для ветки `main`. Для PR-ов CD не триггерится.
- **Uptime.** Если мой компьютер выключен или Minikube лежит — CD упадёт. Для pet-проекта допустимо.
- **Обновления.** GitHub периодически выпускает новые версии runner'а — их нужно обновлять вручную.

## Что сделано для безопасности

- В CD-job'е **нет** прямого доступа к секретам PR-ов. Он срабатывает через `workflow_run` — это защищает от атаки «PR с изменённым workflow».
- Используются секреты **только** через GitHub Secrets → `--set secrets.postgresPassword=...` во время `helm upgrade`.
- Runner запущен как обычный пользователь, не как `root` / `Administrator`.
- Все деплои логируются в Actions — можно посмотреть, что именно выполнялось.

## Alternatives considered

**GitHub-hosted runner + Kubernetes API через public IP.** Требует пробросить `kube-apiserver` в интернет, сгенерировать kubeconfig для runner'а. Для homelab — дыра в безопасности.

**GitHub-hosted runner + Tailscale / ZeroTier.** Работает, но добавляет зависимость от стороннего сервиса. Для pet-проекта — излишняя сложность.

**Отказ от автоматического CD.** Деплой вручную через `helm upgrade` после каждого пуша. Убирает сложность, но теряется «вау-эффект» полного CI/CD. Для портфолио не подходит.

**ArgoCD с auto-sync + GitHub-hosted runner.** ArgoCD сам подтянет изменения из Git, GitHub Actions только собирает образ. Проблема: ArgoCD тоже крутится в Minikube и должен увидеть новый образ. `minikube image load` всё равно требует локального runner'а. Оставлено как Roadmap-пункт.