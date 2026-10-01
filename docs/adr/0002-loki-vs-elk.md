# ADR-0002: Loki + Promtail vs ELK Stack for centralized logs

- **Status:** Accepted
- **Date:** 2026-09
- **Context:** choosing a log aggregation and search stack

## Context

The project runs 9 containers in Kubernetes. It needs centralized logging that:

- Collects logs from all pods in the `opc-monitor` namespace
- Supports regex search and label-based filtering (`pod`, `container`)
- Integrates with Grafana for a single-pane UI
- Does not consume much memory (the whole stack runs in Minikube with 6 GB RAM)
- Correlates well with traces (OpenTelemetry + Jaeger)

## Decision

**Loki + Promtail was chosen.**

Key reasons:

- **Lightweight.** Loki indexes only **labels**, not line content. This dramatically reduces RAM and disk usage compared to Elasticsearch.
- **Native Grafana integration.** Loki is part of the Grafana Labs ecosystem; integration with Grafana Explore is first-class. Single UI: metrics + logs + traces.
- **Promtail** automatically collects logs from `/var/log/containers/*.log` and enriches them with Kubernetes labels (`namespace`, `pod`, `container`, `node`).
- **Excellent trace correlation.** Loki understands `trace_id` as a label and can build links to Jaeger. This is used in the project: a single click from a log entry jumps to the corresponding trace.

## Consequences

**Pros:**

- RAM usage is 5–10× lower than Elasticsearch. Critical for Minikube.
- Single UI (Grafana) for metrics, logs, and traces.
- Simple configuration via ConfigMap.
- Scales horizontally well (Loki is stateless for reads; storage can be offloaded to S3 / MinIO).

**Cons:**

- Full-text search is less powerful than Elasticsearch: Loki does **not** index content, only labels. Regex queries scan data — slower on large volumes.
- Smaller plugin ecosystem than ELK.

**Practical limit:** for our log volume (a few MB/day), Loki's performance is more than sufficient. At tens of GB/day, we would need to tune indexing for key fields.

## Alternatives considered

**ELK (Elasticsearch + Logstash + Kibana)** — industry standard. However:

- Elasticsearch needs ~2 GB RAM at minimum — a third of our entire cluster.
- Logstash is heavy and is commonly replaced by Fluent Bit / Fluentd.
- Kibana is a separate UI, not integrated with Grafana (we would need two windows).

**Fluent Bit + S3 + Athena** — cheap for large volumes, but no real-time search.

**Vector + ClickHouse** — interesting option, but less mainstream and requires a separate UI (Grafana plugin for ClickHouse).