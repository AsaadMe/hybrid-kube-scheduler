.PHONY: buildkind buildimage delkind

buildkind: buildimage dockerpull
	kind create cluster --config kind-cluster-config.yml --image kindest/node:v1.21.12
	kubectl create ns monitoring
	kubectl label node kind-control-plane layer=fog
	kind load docker-image networkstatic/iperf3
	kind load docker-image k8s.gcr.io/metrics-server/metrics-server:v0.6.1
	kind load docker-image hybrid-scheduler:v1
	kind load docker-image nginx:alpine
	kubectl apply -f kub-objects/metric-server.yaml
	kubectl apply -f node-exporter
	kubectl apply -f kub-objects/rbac-scheduler.yaml
	kubectl apply -f kub-objects/hybrid-scheduler-deploy.yaml

dockerpull:
	docker pull networkstatic/iperf3
	docker pull k8s.gcr.io/metrics-server/metrics-server:v0.6.1
	docker pull nginx:alpine

buildimage:
	docker build -t hybrid-scheduler:v1 .

delkind:
	kind delete cluster