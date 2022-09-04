.PHONY: buildkind delkind

buildkind:
	kind create cluster --config kind-cluster-config.yml --image kindest/node:v1.21.12
	kubectl create ns monitoring
	kubectl label node kind-control-plane layer=fog
	kind load docker-image networkstatic/iperf3
	kind load docker-image k8s.gcr.io/metrics-server/metrics-server:v0.6.1
	kind load docker-image ranhema/hybrid-scheduler:v1
	kind load docker-image nginx:alpine
	kubectl apply -f kub-objects/metric-server.yaml
	kubectl apply -f node-exporter
	kubectl apply -f kub-objects/rbac-scheduler.yaml

delkind:
	kind delete cluster