# ADR-0003: k3s vs kind for local and cloud Kubernetes

- **Status:** Accepted
- **Date:** 2026-09
- **Context:** choosing a Kubernetes distribution for local development and cloud deployment

## Context

The project is deployed in two environments:

1. **Locally** — for development and portfolio demonstration. Requirements: fast start, minimal resources, does not break Docker Desktop.
2. **Cloud (Yandex Cloud)** — for Terraform-based IaC. Requirements: real VMs, kubelet on Linux, a chance to demonstrate cloud infrastructure skills.

Helm chart compatibility and the ability to run the full stack (observability, ArgoCD) in one namespace are also important.

## Decision

- **Locally:** Minikube (docker driver).
- **Cloud:** k3s on VMs.

Reasons:

- **Minikube locally** — simplest setup on Windows, does not require WSL2 (though recommended). PersistentVolumeClaims are easy to create via the standard `standard` StorageClass.
- **k3s in cloud** — minimal Kubernetes distribution (~50 MB binary), works well on preemptible VMs with 2 vCPU / 4 GB RAM. Avoids the cost of managed k8s and demonstrates the ability to bring up a control plane manually.
- **kind** is out for cloud: it is designed for CI and local tests, not for a "real" cluster. It also requires Docker-in-Docker on a VM.

## Consequences

**Pros of Minikube locally:**

- Single binary; install via `choco install minikube` or download the exe.
- Supports the docker driver — no Hyper-V / WSL2 required.
- `minikube image load` for local builds without pushing to a registry.
- `minikube tunnel` for LoadBalancer services.

**Pros of k3s in cloud:**

- Minimal RAM footprint (~500 MB for the control plane).
- Bundled Traefik + ServiceLB + local-path-provisioner.
- Simple install: `curl -sfL https://get.k3s.io | sh -`.
- `k3s token` for joining workers — a couple of commands.

**Cons:**

- Minikube does **not** overwrite an image with the same tag on `minikube image load` (see README, "Local Development" section). Workaround: unique tag per build.
- k3s in cloud is a separate infrastructure — upgrades are managed manually (unlike managed k8s).

## Alternatives considered

**kind (Kubernetes in Docker)** — lightweight, widely used in CI. However:

- Requires Docker-in-Docker inside a VM, which complicates setup.
- No built-in LoadBalancer or StorageClass — everything must be installed separately.
- For local development on Windows, Minikube is a more mature DX.

**Docker Desktop Kubernetes** — simple, bundled with Docker Desktop. However:

- Limited configurability (no choice of version, driver, resources).
- Cannot model multi-node setups.

**kubeadm** — the "manual" way. Maximum flexibility, but lots of boilerplate and maintenance time. Overkill for a pet project.

**Managed Kubernetes (Yandex Managed k8s)** — convenient, but expensive (starting at ~5,000 ₽/month for the control plane alone). For demonstrating Terraform skills and a manual k3s setup, self-managed is more illustrative.