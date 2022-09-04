from kubernetes import client, config
from collections import Counter, defaultdict
import random
import cluster
import yaml
import nsgaiii

try:
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
except:
    pass


def objective_1(x):
    x = x.replace('0','')
    count = Counter(x)
    return sum([a*(a+1)/2 for a in count.values()])

def objective_2(x):
    ans_sum = 0
    nds = defaultdict(list)
    for i, e in enumerate(x):
        if e != '0':
            nds[e].append(containers['c'+str(i+1)].app_name)
            
    for typelist in nds.values():
        c = Counter(typelist)
        ans_sum += sum([a*(a+1)/2 for a in c.values()])
    
    return ans_sum

def objective_3(x):
    
    def get_power(node_cpu, node_memory):
        PCPU = 0.3
        PMEM = 0.11
        PIDLE_TOTAL_REF = 171
        PMAX_TOTAL_REF = 218
        CORES_REF = 4
        MEM_REF = 4000
        
        pidle_cpu_ref = PIDLE_TOTAL_REF * PCPU
        pidle_mem_ref = PIDLE_TOTAL_REF * PMEM
        delta_pidle_cpu = (pidle_cpu_ref * node_cpu / CORES_REF) - pidle_cpu_ref
        delta_pidle_mem = (pidle_mem_ref * node_memory / MEM_REF) - pidle_mem_ref
        pidle_total = PIDLE_TOTAL_REF + delta_pidle_cpu + delta_pidle_mem
    
        pmax_cpu_ref = PMAX_TOTAL_REF * PCPU
        pmax_mem_ref = PMAX_TOTAL_REF * PMEM
        delta_pmax_cpu = (pmax_cpu_ref * node_cpu / CORES_REF) - pmax_cpu_ref
        delta_pmax_mem = (pmax_mem_ref * node_memory / MEM_REF) - pmax_mem_ref
        pmax_total = PMAX_TOTAL_REF + delta_pmax_cpu + delta_pmax_mem
    
        return pidle_total, pmax_total
    
    all_power = 0
    nds = defaultdict(list)
    for i, e in enumerate(x):
        if e != '0':
            nds[e].append([containers['c'+str(i+1)].req_cpu, containers['c'+str(i+1)].req_mem])
    
    for nid, usage in nds.items():
        cntrs_use_cpu = sum([a[0] for a in usage])
        cntrs_use_mem = sum([a[1] for a in usage])
        
        cpu_usage_util = (nodes['n'+nid].inuse_cpu + cntrs_use_cpu) / nodes['n'+nid].spec_cpu
        mem_usage_util = (nodes['n'+nid].inuse_mem + cntrs_use_mem) / nodes['n'+nid].spec_mem
        
        idle_power, max_power = get_power(nodes['n'+nid].spec_cpu, nodes['n'+nid].spec_mem)
        
        all_power += (max_power - idle_power) * (cpu_usage_util + mem_usage_util)/2 + idle_power
        
    return all_power

def objective_4(x):
    nds = defaultdict(list)
    nds_free_cpu_percs = []
    nds_free_mem_percs = []
    for i, e in enumerate(x):
        if e != '0':
            nds[e].append([containers['c'+str(i+1)].req_cpu, containers['c'+str(i+1)].req_mem])

    for nid, usage in nds.items():
        cntrs_use_cpu = sum([a[0] for a in usage])
        cntrs_use_mem = sum([a[1] for a in usage])
        
        free_cpu_perc = abs(nodes['n'+nid].get_rem_cpu() - cntrs_use_cpu)/nodes['n'+nid].spec_cpu
        free_mem_perc = abs(nodes['n'+nid].get_rem_mem() - cntrs_use_mem)/nodes['n'+nid].spec_mem
        
        nds_free_cpu_percs.append(free_cpu_perc)
        nds_free_mem_percs.append(free_mem_perc)
        
    return sum([abs(a-b) for a,b in zip(nds_free_cpu_percs, nds_free_mem_percs)])/len(nodes) * 100

def objective_5(x):
    return x.count('0')

def objective_6(x):
    x = x.replace('0','')
    count = Counter(x)
    return -sum([c*nodes['n'+n].bitrate for n,c in count.items()])

def get_containers():
    v1 = client.CoreV1Api()
    containers = []
    
    # cpu in mili, memory in Mi
    for id, pod in enumerate(v1.list_namespaced_pod('default').items, 1):
        pod_name = pod.metadata.name
        app_name = pod.metadata.labels['app']
        req_cpu = float(pod.spec.containers[0].resources.requests['cpu'][:-1]) / 1000
        req_memory = float(pod.spec.containers[0].resources.requests['memory'][:-2])
        containers.append(cluster.Container('c'+str(id), pod_name, app_name, req_cpu, req_memory))
        
    return containers

def test_default_scheduler():    
    v1_a = client.CoreV1Api()
    v1_b = client.AppsV1Api()
    with open('../kub-objects/evaluate-nginx-deploy.yaml', 'r') as ymlfile:
        data = yaml.safe_load_all(ymlfile)
        app_a, app_b = data
    
    app_a['spec']['template']['spec']['schedulerName'] = 'default-scheduler'
    app_b['spec']['template']['spec']['schedulerName'] = 'default-scheduler'
    
    eval_score = []
    
    try:
        v1_b.create_namespaced_deployment(body=app_a, namespace='default')
        v1_b.create_namespaced_deployment(body=app_b, namespace='default')
        
        all_pods = {}
        pod_items = v1_a.list_namespaced_pod('default').items
        while (not all([p.status.phase == 'Running' for p in pod_items]) and 
               len(pod_items) != app_a['spec']['replicas'] + app_b['spec']['replicas']):
            pod_items = v1_a.list_namespaced_pod('default').items

        pod_items = v1_a.list_namespaced_pod('default').items

        for pod in pod_items:
            if pod.metadata.labels.get('app').startswith('nginx'):
                all_pods[pod.metadata.name] = {"node":pod.spec.node_name}
        
        global nodes, containers        
        nodes = {n.id: n for n in cluster.get_nodes(get_disk=False)}
        nds_name_id = {n.name:n.id[1:] for n in nodes.values()}
        containers = {c.id: c for c in get_containers()}
        state = ['0']*len(containers)
        
        for pod in containers.values():
            state[int(pod.id[1:])-1] = nds_name_id[all_pods[pod.name]['node']]
                
        objs = [objective_1,
                objective_2,
                objective_3,
                objective_4,
                objective_5,
                ]
        
        state = ''.join(state)
        print(state)
        for obj in objs:
            eval_score.append(obj(state))
        
    finally:    
        v1_b.delete_namespaced_deployment(name=app_a['metadata']['name'], namespace='default')
        v1_b.delete_namespaced_deployment(name=app_b['metadata']['name'], namespace='default')
    
    return eval_score

def run_eval_on_real_cluster():
    v1 = client.CoreV1Api()
    all_res = [[],[],[],[],[]]
    while len(all_res[0]) != 10:
        if not v1.list_namespaced_pod('default').items:
            res = test_default_scheduler()
            for i, sc in enumerate(res):
                all_res[i].append(sc)
                
    print([sum(a)/len(a) for a in all_res])
    
    
############

def filter_nodes(nodes, pod):
    ret = []
    for node in nodes:
        if node.get_rem_cpu() >= pod.req_cpu and node.get_rem_mem() >= pod.req_mem:
            ret.append(node)
    return ret


def random_schedule(nodes, pods):
    fin_state = ['0']*len(pods)
    for pod in pods:
        acc_nodes = filter_nodes(nodes, pod)
        if acc_nodes:
            sch_node = random.choice(acc_nodes)
            sch_node.inuse_cpu += pod.req_cpu
            sch_node.inuse_mem += pod.req_mem
            fin_state[int(pod.id[1:])-1] = str(int(sch_node.id[1:]))
    
    return ''.join(fin_state)    

def spread_schedule(nodes, pods):
    fin_state = ['0']*len(pods)
    for pod in pods:
        acc_nodes = filter_nodes(nodes, pod)
        if acc_nodes:
            d = [n.get_rem_cpu()**2 + n.get_rem_mem()**2 for n in acc_nodes]
            sch_node = acc_nodes[d.index(min(d))]
            sch_node.inuse_cpu += pod.req_cpu
            sch_node.inuse_mem += pod.req_mem
            fin_state[int(pod.id[1:])-1] = str(int(sch_node.id[1:]))
    
    return ''.join(fin_state)

def binpack_schedule(nodes, pods):
    fin_state = ['0']*len(pods)
    for pod in pods:
        acc_nodes = filter_nodes(nodes, pod)
        if acc_nodes:
            d = [n.get_rem_cpu()**2 + n.get_rem_mem()**2 for n in acc_nodes]
            sch_node = acc_nodes[d.index(max(d))]
            sch_node.inuse_cpu += pod.req_cpu
            sch_node.inuse_mem += pod.req_mem
            fin_state[int(pod.id[1:])-1] = str(int(sch_node.id[1:]))
    
    return ''.join(fin_state)


def run_eval_on_simul_cluster(n_nodes, n_pods, schedule_func):
    algos = {'spread':spread_schedule, 'random':random_schedule, 'binpack':binpack_schedule}
    global nodes, containers
    nds = cluster.get_all_simul_nodes(n_nodes)
    pods = cluster.get_all_simul_containers(n_pods)
    nodes = {n.id:n for n in nds}
    containers = {c.id:c for c in pods}
    state = algos[schedule_func](nds, pods)
    return state

    
def main():
    num_tests = 1000
    num_nodes, num_pods = 6, 8
    objs = [
            objective_2,
            objective_3,
            objective_4,
            objective_5,
            objective_6
            ]
    all_evals_random = [[],[],[],[],[]]
    for _ in range(num_tests):
        st = run_eval_on_simul_cluster(num_nodes, num_pods, 'random')
        for i, obj in enumerate(objs):
                all_evals_random[i].append(obj(st))

    average_evals_random = [sum(a)/len(a) for a in all_evals_random]
    
    all_evals_spread = [[],[],[],[],[]]
    for _ in range(num_tests):
        st = run_eval_on_simul_cluster(num_nodes, num_pods, 'spread')
        for i, obj in enumerate(objs):
                all_evals_spread[i].append(obj(st))

    average_evals_spread = [sum(a)/len(a) for a in all_evals_spread]
    
    all_evals_binpack = [[],[],[],[],[]]
    for _ in range(num_tests):
        st = run_eval_on_simul_cluster(num_nodes, num_pods, 'binpack')
        for i, obj in enumerate(objs):
                all_evals_binpack[i].append(obj(st))

    average_evals_binpack = [sum(a)/len(a) for a in all_evals_binpack]
    
    all_evals_nsgaiii = [[],[],[],[],[]]
    fail_count = 0
    for j in range(50):
        # print(f'NSGAIII try {j}th test.', end='\r')
        try:
            st = nsgaiii.for_test(num_nodes, num_pods)
            print(st)
            for i, obj in enumerate(objs):
                all_evals_nsgaiii[i].append(obj(st))
        except:
            fail_count += 1
        
    print(f'NSGAIII failed {fail_count} times.')
    average_evals_nsgaiii = [sum(a)/len(a) for a in all_evals_nsgaiii]
    
    print(average_evals_random)
    print(average_evals_spread)
    print(average_evals_binpack)
    print(average_evals_nsgaiii)
    
if __name__ == '__main__':
    main()