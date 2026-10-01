# ADR-0004: Self-hosted runner vs GitHub-hosted for CD

- **Status:** Accepted
- **Date:** 2026-09
- **Context:** choosing a runner for the deployment job against local Minikube

## Context

The project uses CI/CD via GitHub Actions:

- **CI job** (`test` + `build` + `trivy`) — fully isolated, operates on sources and Docker images. Can run on a GitHub-hosted runner.
- **CD job** (`deploy`) — deploys to **local Minikube** running on my machine. It needs to:

  - Pull the image from GHCR
  - Load it into Minikube (`minikube image load`)
  - Update the Helm release in the current kube-context
  - Wait for `rollout status`

A GitHub-hosted runner **cannot** do any of this — it is virtual and has no access to my Minikube.

## Decision

**CI runs on GitHub-hosted runners; CD runs on a self-hosted runner (my machine).**

Reasons:

- **Free.** Self-hosted runners are not billed by GitHub Actions minutes. Important for a pet project — otherwise a CD job at 50–60 seconds accumulates in billing.
- **Direct access to Minikube.** The self-hosted runner runs inside my network and sees Docker Desktop and Minikube on localhost.
- **Realistic scenario.** This pattern appears frequently in enterprises: GitHub-hosted for CI, self-hosted behind a VPN for internal cluster deployments.

## Consequences

**Pros:**

- CD runs fast (~50 sec) — the image is already in GHCR, pulled and loaded into Minikube in seconds.
- No need to expose Minikube ports to the internet (self-hosted runner is egress-only).
- Realistic demonstration: shows I can set up a runner and document its installation in the README.

**Cons and risks:**

- **Security.** The self-hosted runner runs **on my machine** under my user. If someone could push a PR with a modified workflow, they could theoretically execute arbitrary code. **Mitigation:** the workflow triggers only on `workflow_run` after CI, and only for the `main` branch. PRs do not trigger CD.
- **Uptime.** If my computer is off or Minikube is down, CD fails. Acceptable for a pet project.
- **Updates.** GitHub periodically releases new runner versions — they need to be upgraded manually.

## What was done for security

- The CD job has **no** direct access to PR secrets. It triggers via `workflow_run`, which protects against the "PR with modified workflow" attack.
- Secrets are consumed **only** through GitHub Secrets → `--set secrets.postgresPassword=...` during `helm upgrade`.
- The runner runs as a regular user, not as `root` / `Administrator`.
- All deployments are logged in Actions — the exact commands can be inspected afterwards.

## Alternatives considered

**GitHub-hosted runner + Kubernetes API over public IP.** Requires exposing `kube-apiserver` to the internet and generating a kubeconfig for the runner. For a homelab this is a security hole.

**GitHub-hosted runner + Tailscale / ZeroTier.** Works, but adds a third-party service dependency. Overkill for a pet project.

**No automated CD.** Manual `helm upgrade` after each push. Removes complexity but loses the "full CI/CD" wow-factor. Not suitable for portfolio.

**ArgoCD with auto-sync + GitHub-hosted runner.** ArgoCD would pick up changes from Git itself; GitHub Actions would only build the image. Problem: ArgoCD also runs in Minikube and must see the new image. `minikube image load` still requires a local runner. Kept as a Roadmap item.