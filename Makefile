.PHONY: buildkind delkind

buildkind:
	kind create cluster --config kind-cluster-config.yml
	kubectl create ns monitoring
	kubectl label node kind-control-plane layer=fog
	kind load docker-image networkstatic/iperf3
	kubectl apply -f metric-server.yaml
	kubectl apply -f node-exporter

delkind:
	kind delete cluster