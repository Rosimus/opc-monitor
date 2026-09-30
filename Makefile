.PHONY: help test test-fast lint build deploy-local destroy rollback logs status

help:
	@echo "Available commands:"
	@echo "  make test         - run tests with coverage"
	@echo "  make test-fast    - run tests without coverage"
	@echo "  make lint         - bandit + hadolint"
	@echo "  make build        - build Docker image"
	@echo "  make deploy-local - deploy to current kube-context via Helm"
	@echo "  make rollback     - rollback last Helm release"
	@echo "  make status       - show pods in opc-monitor namespace"
	@echo "  make logs         - tail web pod logs"
	@echo "  make destroy      - uninstall Helm release"

NAMESPACE ?= opc-monitor
RELEASE   ?= opc-monitor
CHART     ?= ./helm/opc-monitor
VALUES    ?= $(CHART)/values-prod.yaml

test:
	pytest tests/ -v --cov=. --cov-report=term-missing

test-fast:
	pytest tests/ -v

lint:
	bandit -r . -c .bandit
	hadolint Dockerfile

build:
	docker build -t opc-monitor:latest .

deploy-local:
	helm upgrade --install $(RELEASE) $(CHART) \
		-n $(NAMESPACE) --create-namespace \
		-f $(VALUES)

rollback:
	helm rollback $(RELEASE) -n $(NAMESPACE)

status:
	kubectl get pods -n $(NAMESPACE)

logs:
	kubectl logs -n $(NAMESPACE) deployment/web --tail=100

destroy:
	helm uninstall $(RELEASE) -n $(NAMESPACE)