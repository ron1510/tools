HELM_RELEASE_NAME ?= gremlin-arangodb-poc
KUBE_NAMESPACE ?= gremlin-lab
CHART_PATH ?= charts/gremlin-arangodb-poc
ARANGODB_CHART_PATH ?= charts/arangodb-lab
GREMLIN_SERVER_PORT ?= 8182
ARANGODB_URL ?= http://127.0.0.1:8529
PYTHON ?= python

.PHONY: helm-template helm-install helm-upgrade helm-uninstall arangodb-install arangodb-upgrade arangodb-uninstall seed-arangodb kubectl-logs port-forward smoke shell logs

helm-template:
	helm template $(HELM_RELEASE_NAME) $(CHART_PATH) --namespace $(KUBE_NAMESPACE)

helm-install:
	helm install $(HELM_RELEASE_NAME) $(CHART_PATH) --namespace $(KUBE_NAMESPACE) --create-namespace

helm-upgrade:
	helm upgrade --install $(HELM_RELEASE_NAME) $(CHART_PATH) --namespace $(KUBE_NAMESPACE) --create-namespace

helm-uninstall:
	helm uninstall $(HELM_RELEASE_NAME) --namespace $(KUBE_NAMESPACE)

arangodb-install:
	helm install arangodb-lab $(ARANGODB_CHART_PATH) --namespace $(KUBE_NAMESPACE) --create-namespace

arangodb-upgrade:
	helm upgrade --install arangodb-lab $(ARANGODB_CHART_PATH) --namespace $(KUBE_NAMESPACE) --create-namespace

arangodb-uninstall:
	helm uninstall arangodb-lab --namespace $(KUBE_NAMESPACE)

seed-arangodb:
	$(PYTHON) scripts/seed_arangodb.py --url $(ARANGODB_URL)

kubectl-logs logs:
	kubectl logs -n $(KUBE_NAMESPACE) deployment/$(HELM_RELEASE_NAME) -f

port-forward:
	kubectl port-forward -n $(KUBE_NAMESPACE) service/$(HELM_RELEASE_NAME) $(GREMLIN_SERVER_PORT):8182

smoke:
	$(PYTHON) scripts/smoke_test.py --uri ws://localhost:$(GREMLIN_SERVER_PORT)/gremlin

shell:
	kubectl exec -it -n $(KUBE_NAMESPACE) deployment/$(HELM_RELEASE_NAME) -- /bin/bash
