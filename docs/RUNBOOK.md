# OPC Monitor — Runbook

Инструкция для инженера on-call по диагностике и восстановлению системы.

## 📊 SLO / SLI

| Метрика | SLI | SLO | Как измеряется |
|---------|-----|-----|----------------|
| **Доступность Web UI** | `up{job="opc-monitor"}` | ≥ 99% в месяц | Prometheus |
| **Доступность OPC Client** | `up{job="opc-client"}` | ≥ 99% в месяц | Prometheus |
| **Латентность API (p95)** | `histogram_quantile(0.95, api_latency_seconds_bucket)` | < 500 ms | Prometheus |
| **Задержка сбора данных** | `rate(opc_values[5m])` | > 0 (данные идут) | Prometheus |
| **RTO** (Recovery Time Objective) | — | ≤ 5 минут | helm rollback |
| **RPO** (Recovery Point Objective) | — | ≤ 24 часа | pg_dump ежедневно |

**Error Budget:** 1% недоступности в месяц = ~7.2 часа.

---

## 🚨 Алерты и реакции

### Alert: `ServiceDown`

**Severity:** critical

**Что значит:** один из сервисов (`web`, `client`, `alertmanager`) не отвечает Prometheus более 1 минуты.

**Диагностика:**

```bash
# 1. Статус подов
kubectl get pods -n opc-monitor

# 2. Логи проблемного сервиса
kubectl logs -n opc-monitor deployment/<service> --tail=50

# 3. События пода
kubectl describe pod -n opc-monitor -l app=<service> | tail -30