# Kubernetes Hybrid Scheduler

- This scheduler uses NSGA-III algorithm to select best nodes to place batch of pods into.
- Pods with 3 or fewer replicas or the ones for which nsga couldn't find an optimal solution will be scheduled in serial by TOPSIS algorithm.
- Scheduler.py uses Operator pattern to watch cluster state and system metrics.
- Using metrics-server, prometheus node exporter and iperf3.
- Results:
  - Increased Availability, Reliability and Scalability of the system.
  - Reduced power consumption of nodes and communication delay.

<br/>

- Use KIND as local kubernetes cluster -> `make buildkind`
- Use `schedulerName: hybrid-scheduler` and custom resources requests in pod configurations ([example](kub-objects/nginx-deploy.yaml)).

<br/>

![Architecture](doc/custom-scheduler.png)