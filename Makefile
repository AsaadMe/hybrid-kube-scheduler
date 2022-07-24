.PHONY: buildkind delkind

buildkind:
	kind create cluster --config kind-cluster-config.yml --image kindest/node:v1.21.12
	kubectl create ns monitoring
	kubectl label node kind-control-plane layer=fog
	kind load docker-image networkstatic/iperf3
	kubectl apply -f kub-objects/metric-server.yaml
	kubectl apply -f node-exporter
	kubectl apply -f kub-objects/rbac-scheduler.yaml

delkind:
	kind delete cluster