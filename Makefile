.PHONY: buildkind delkind

buildkind:
	kind create cluster --config kind-cluster-config.yml
	kubectl create ns monitoring
	kubectl label node kind-control-plane layer=fog
	kind load docker-image networkstatic/iperf3
	kubectl apply -f kub-objects/metric-server.yaml
	kubectl apply -f node-exporter
	kubectl apply -f kub-objects/rbac-scheduler.yaml

delkind:
	kind delete cluster