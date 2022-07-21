from kubernetes import client, config
from kubernetes.stream import stream

from collections import defaultdict
import random
import time
import json
import yaml

try:
    config.load_incluster_config()
except:
    config.load_kube_config()
    
class Node:
    def __init__(self, id, name, spec_cpu, spec_mem, inuse_cpu=0, inuse_mem=0):
        self.id = id
        self.name = name
        self.spec_cpu = spec_cpu
        self.spec_mem = spec_mem
        self.inuse_cpu = inuse_cpu    
        self.inuse_mem = inuse_mem
    
    def __repr__(self) -> str:
        return f"Node(ID: {self.id}, Spec: <{self.spec_cpu}, {self.spec_mem}>)"
        
    def get_rem_cpu(self):
        return self.spec_cpu - self.inuse_cpu
    
    def get_rem_mem(self):
        return self.spec_mem - self.inuse_mem
    
                    
class Container:
    def __init__(self, id, name, app_name, req_cpu, req_mem):
        self.id = id
        self.name = name
        self.app_name = app_name
        self.req_cpu = req_cpu
        self.req_mem = req_mem
    
    def __repr__(self) -> str:
        return f"Container(ID: {self.id}, App: {self.app_name}, req: <{self.req_cpu}, {self.req_mem}>)"    

def get_all_simul_nodes():
    nodes = []
    possible_cpu = range(1,9)
    possible_mem = [1000, 2000, 4000, 8000, 10000, 12000]
    for i in range(1,6):
        nodes.append(Node("n"+str(i), "n"+str(i), random.choice(possible_cpu), random.choice(possible_mem)))
        
    return nodes

def get_all_simul_containers():
    containers = []
    possible_req_cpu = range(1,5)
    possible_req_mem = range(100, 4000, 200)
    possible_apps = ["app1", "app2"]
    for i in range(1,7):
        containers.append(Container("c"+str(i), "c"+str(i), random.choice(possible_apps), random.choice(possible_req_cpu), random.choice(possible_req_mem)))
        
    return containers

def get_nodes():
    v1 = client.CoreV1Api()
    cust = client.CustomObjectsApi()

    metrics = cust.list_cluster_custom_object('metrics.k8s.io', 'v1beta1', 'nodes')

    cluster_nodes = defaultdict(dict)
    
    # n = nano cores, Ki = kilobytes
    for stats in metrics['items']:
        node_name = stats['metadata']['name']
        cluster_nodes[node_name]['used_cpu'] = float(stats['usage']['cpu'][:-1]) / 10**9
        cluster_nodes[node_name]['used_memory'] = float(stats['usage']['memory'][:-2]) / 10**3
        
        
    for node in v1.list_node().items:
        node_name = node.status.addresses[1].address
        cluster_nodes[node_name]['spec_cpu'] = float(node.status.allocatable['cpu'])
        cluster_nodes[node_name]['spec_memory'] = float(node.status.allocatable['memory'][:-2]) / 10**3
    
    nodes = []
    for id, (name, info) in enumerate(cluster_nodes.items(), 1):
        node = Node('n'+str(id), name, info['spec_cpu'], info['spec_memory'], info['used_cpu'], info['used_memory'])
        nodes.append(node)
        
    return nodes

def get_pending_containers():
    v1 = client.CoreV1Api()
    containers = []
    
    # cpu in mili, memory in Mi
    for id, pod in enumerate(v1.list_pod_for_all_namespaces().items, 1):
        if pod.status.phase == 'Pending':
            pod_name = pod.metadata.name
            app_name = pod.metadata.labels['app']
            req_cpu = float(pod.spec.containers[0].resources.requests['cpu'][:-1]) / 1000
            req_memory = float(pod.spec.containers[0].resources.requests['memory'][:-2])
            containers.append(Container('c'+str(id), pod_name, app_name, req_cpu, req_memory))
        
    return containers

def pod_exec(name, namespace, command, api_instance):
    exec_command = ["/bin/sh", "-c", command]

    resp = stream(api_instance.connect_get_namespaced_pod_exec,
                  name,
                  namespace,
                  command=exec_command,
                  stderr=True, stdin=False,
                  stdout=True, tty=False,
                  _preload_content=False)

    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            output = resp.read_stdout()
        if resp.peek_stderr():
            print(f"STDERR: \n{resp.read_stderr()}")

    resp.close()

    if resp.returncode != 0:
        raise Exception("Script failed")
    
    return output

def get_network_bitrate():
    # bitrate (Gbits/sec) of each node to master
    
    v1_a = client.CoreV1Api()
    v1_b = client.AppsV1Api()
    with open('iperf3.yaml','r') as ymlfile:
        data = yaml.safe_load_all(ymlfile)
        dep, serv, dmset = data
        
    v1_b.create_namespaced_deployment(body=dep, namespace='default')
    v1_a.create_namespaced_service(body=serv, namespace='default')
    v1_b.create_namespaced_daemon_set(body=dmset, namespace='default')
    
    clients = []
    while True:
        check_ready = 0
        pod_items = v1_a.list_namespaced_pod('default').items
        for pod in pod_items:
            if pod.metadata.labels.get('app') == 'iperf3-client' and pod.status.container_statuses:
                if pod.status.container_statuses[0].ready:
                    check_ready += 1

        if check_ready == len(v1_a.list_node().items)-1:
            for pod in pod_items:
                if pod.metadata.labels.get('app') == 'iperf3-client' and pod.status.container_statuses[0].ready:
                    clients.append({'name':pod.metadata.name, 'node': pod.spec.node_name, 'ip':pod.status.host_ip})
            break

    for cli in clients:
        cmd = f"iperf3 -c iperf3-server --json -T 'Client on {cli['ip']}'"
        while True:
            try:
                output = json.loads(pod_exec(cli['name'], "default", cmd, v1_a))
                break
            except:
                pass
        cli['bitrate'] = output['end']['sum_received']['bits_per_second'] / 10**9  #Gbits/sec
        
    v1_b.delete_namespaced_deployment(name=dep['metadata']['name'], namespace='default')
    v1_a.delete_namespaced_service(name=serv['metadata']['name'], namespace='default')
    v1_b.delete_namespaced_daemon_set(name=dmset['metadata']['name'], namespace='default')
    
    return [{'node':n['node'], 'bitrate':n['bitrate']} for n in clients]