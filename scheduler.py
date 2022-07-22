#!/usr/bin/env python3

from kubernetes import client, config
import datetime
import time

import cluster
import topsis

try:
    config.load_incluster_config()
except:
    config.load_kube_config()
    
v1 = client.CoreV1Api()

def nodes_available():
    ready_nodes = []
    for n in v1.list_node().items:
            for status in n.status.conditions:
                if status.status == "True" and status.type == "Ready":
                    ready_nodes.append(n.metadata.name)
    return ready_nodes


def schedule(name, node, namespace='default'):
    target = client.V1ObjectReference(kind = 'Node', api_version = 'v1', name = node)
    meta = client.V1ObjectMeta(name = name)
    body = client.V1Binding(api_version=None, kind=None, target=target, metadata=meta)

    event_involved_object = client.V1ObjectReference(kind='Pod', api_version='v1', name=name, namespace=namespace)
    event_timestamp = datetime.datetime.now(datetime.timezone.utc)
    event_meta = client.V1ObjectMeta(name=name, creation_timestamp=event_timestamp)
    event_source = client.V1EventSource(component='hybrid-scheduler')
    event_message = f"Successfully assigned default/{name} to {node}"
    event = client.CoreV1Event(message=event_message,metadata=event_meta, involved_object=event_involved_object,
                               first_timestamp=event_timestamp, reason='Scheduled', source=event_source, type='Normal')
    v1.create_namespaced_event('default', event)

    return v1.create_namespaced_pod_binding(name, namespace=namespace, body=body, _preload_content=False)

def schedule_topsis(pod):
    nodes = cluster.get_nodes()
    attrs = {n.name:{'memory':n.get_rem_mem(), 'cpu_core':n.get_rem_cpu(),
                    'disk_total':n.disk_total, 'disk_free':n.disk_free,
                    'bitrate':n.bitrate} for n in nodes}
    
    best = topsis.best_host(attrs)
    schedule(pod, best)
        
        
def schedule_nsgaiii(pods):
    pass

def main():
    
    scheduler_name = "hybrid-scheduler"

    pods_to_schedule = []
    while True: # main loop
        tmp_pods = []
        pod_items = v1.list_namespaced_pod('default').items
        for pod in pod_items:
            if pod.status.phase == 'Pending' and pod.status.conditions == None and pod.spec.scheduler_name == scheduler_name:
                tmp_pods.append(pod.metadata.name)
        
        if tmp_pods and (pods_to_schedule == tmp_pods):
            if len(pods_to_schedule) <= 3:
                for p in pods_to_schedule:
                    try:
                        schedule_topsis(p)
                    except:
                        pass
            else:
                try:
                    schedule_nsgaiii(pods_to_schedule)
                except:
                    pass
            pods_to_schedule = []
        else:
            pods_to_schedule = tmp_pods
            time.sleep(0.5)
        
                 
if __name__ == '__main__':
    main()
