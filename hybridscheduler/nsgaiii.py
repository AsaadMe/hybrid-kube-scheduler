from pymoo.factory import get_reference_directions, get_selection
from pymoo.core.duplicate import ElementwiseDuplicateElimination
from pymoo.operators.selection.tournament import compare
from pymoo.mcdm.pseudo_weights import PseudoWeights
from pymoo.core.problem import ElementwiseProblem
from pymoo.visualization.scatter import Scatter
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.core.crossover import Crossover
from pymoo.core.sampling import Sampling
from pymoo.core.mutation import Mutation
from pymoo.optimize import minimize

from pyrecorder.writers.video import Video
from pyrecorder.recorder import Recorder

import numpy as np
from numpy.random import default_rng
rng = default_rng()

from collections import Counter, defaultdict


nodes = None
containers = None

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
            
   
def feasibility(x):
    constraint_violation = 0
    constraint_sum_cpu = 0
    constraint_sum_mem = 0
    inuse_nodes = [[0,0] for _ in range(len(nodes))]
    for container_id, node_id in enumerate(x, 1):
        if node_id != '0':
            inuse_nodes[int(node_id)-1][0] += containers['c'+str(container_id)].req_cpu
            inuse_nodes[int(node_id)-1][1] += containers['c'+str(container_id)].req_mem
        
    for nid, (ncpu, nmem) in enumerate(inuse_nodes, 1):
        rem_cpu = nodes['n'+str(nid)].get_rem_cpu()
        rem_mem = nodes['n'+str(nid)].get_rem_mem()
        if ncpu > rem_cpu or nmem > rem_mem:
            constraint_violation += 1
            if ncpu > rem_cpu:
                constraint_sum_cpu += ncpu - rem_cpu
            if nmem > rem_mem:
                constraint_sum_mem += nmem - rem_mem
            
    return constraint_violation, constraint_sum_cpu, constraint_sum_mem


class MyProblem(ElementwiseProblem):

    def __init__(self, n_characters, **kargs):
        super().__init__(n_var=1, n_obj=5, n_constr=1)
        self.n_characters = n_characters
        self.ALPHABET = [str(c+1) for c in range(len(nodes))]

    def _evaluate(self, X, out, *args, **kwargs):
        X = X[0]
        all_objectives = [objective_2, objective_3, objective_4, objective_5, objective_6]

        out["F"] = [obj_func(X) for obj_func in all_objectives]
        out["G"] = list(feasibility(X)[0:1])
        
class MySampling(Sampling):

    def _do(self, problem, n_samples, **kwargs):
        X = np.full((n_samples, 1), None, dtype=object)

        for i in range(n_samples):
            X[i, 0] = "".join([rng.choice(problem.ALPHABET) for _ in range(problem.n_characters)])

        return X
    
class MyCrossover(Crossover):
    def __init__(self):

        # define the crossover: number of parents and number of offsprings
        super().__init__(2, 1)

    def _do(self, problem, X, **kwargs):

        # The input of has the following shape (n_parents, n_matings, n_var)
        _, n_matings, n_var = X.shape

        Y = np.full((1, n_matings, 1), None, dtype=object)

        # for each mating provided
        for k in range(n_matings):

            # get the first and the second parent
            a, b = X[0, k, 0], X[1, k, 0]

            single_point = rng.integers(1, problem.n_characters)
            offspring = a[:single_point] + b[single_point:] 
            
            # set the output
            Y[0, k, 0] = offspring

        return Y
    
class MyMutation(Mutation):
    def __init__(self):
        super().__init__()

    def _do(self, problem, X, **kwargs):

        X = X[:int(len(X)/2)]
        
        # for each individual
        for i in range(len(X)):
            if rng.random() <= 0.5: # OR 0.3
                
                r = rng.random()
            
                if r <= 0.25: # change
                    ind = list(X[i, 0])
                    while (ch_index := rng.integers(0, problem.n_characters)) != '0':
                        psbl_char = list(set(problem.ALPHABET) - set(ind[ch_index]))
                        ind[ch_index] = rng.choice(psbl_char)
                        break 
                    
                    X[i, 0] = "".join(ind)
                
                elif (r > 0.25 and r <= 0.5): # swap
                    while True:
                        a, b = rng.integers(0, problem.n_characters, 2)
                        if a != b:
                            ind = list(X[i, 0])
                            ind[a], ind[b] =  ind[b], ind[a]
                            X[i, 0] = "".join(ind)
                            break
                        
                elif (r > 0.5 and r <= 0.51):
                    if not feasibility(X[i, 0])[0]: # unassignAssigned
                        ind = list(X[i, 0])
                        mut_index = rng.integers(0, problem.n_characters)
                        if ind[mut_index] != "0":
                            ind[mut_index] = "0"
                            X[i, 0] = "".join(ind)
                            
                elif (r > 0.51 and r <= 1.0):
                    ind = list(X[i, 0])
                    none_indexes = []
                    if ind.count("0") > 0: # assignUnassigned
                        for index, j in enumerate(ind):
                            if j == "0":
                                none_indexes.append(index)
                        
                        ind[rng.choice(none_indexes)] = rng.choice(problem.ALPHABET)
                        X[i, 0] = "".join(ind)
        return X
    
class MyDuplicateElimination(ElementwiseDuplicateElimination):
    def is_equal(self, a, b):
        return a.X[0] == b.X[0]

def mybinary_tournament(pop, P, **kwargs):

    S = np.full(P.shape[0], np.nan)

    for i in range(P.shape[0]):
        a, b = P[i, 0], P[i, 1]

        # if at least one solution is infeasible
        if pop[a].CV > 0.0 or pop[b].CV > 0.0:
            S[i] = compare(a, pop[a].CV, b, pop[b].CV, method='smaller_is_better', return_random_if_equal=True)

        # both solutions are feasible just set random
        elif pop[a].F[4] < pop[b].F[4]:
            S[i] = a
        else:
            S[i] = b

    return S[:, None].astype(int)

def record_generation_video(minimize_result):
    with Recorder(Video("ga.mp4", fps=5)) as rec:

        # for each algorithm object in the history
        for entry in minimize_result.history:
            sc = Scatter(title=("Gen %s" % entry.n_gen), figsize=(15,15), tight_layout=True)
            sc.add(entry.pop.get("F"), s=15)
            sc.do()

            # finally record the current visualization to the video
            rec.record()


def schedule(nds, contrs):
    global nodes, containers
    nodes = nds
    containers = contrs  
      
    # (5, 6) = (M, p) = (n_obj, #of divisions) -> H = C(M+p-1, p)
    ref_dirs = get_reference_directions("das-dennis", 5, n_partitions=6)
    algorithm = NSGA3(pop_size=212,
                    sampling=MySampling(),
                    selection=get_selection('tournament', func_comp=mybinary_tournament),
                    crossover=MyCrossover(),
                    mutation=MyMutation(),
                    eliminate_duplicates=MyDuplicateElimination(),
                    ref_dirs=ref_dirs)
  
    res = minimize(MyProblem(n_characters=len(containers)),
                algorithm,
                ('n_gen', 100),
                seed=1,
                return_least_infeasible=False,
                verbose=False)

    # results = res.X[np.argsort(res.F[:, 0])]
    # return results[-1][0]

    ref_dirs = get_reference_directions("das-dennis", 5, n_partitions=6)
    F = res.F

    weights = np.array([0.15, 0.15, 0.15, 0.4, 0.15])
    a, _ = PseudoWeights(weights).do(F, return_pseudo_weights=True)
    return res.X[a][0]
    

def for_test(n_nodes, n_pods):
    from cluster import get_all_simul_nodes, get_all_simul_containers
    
    global nodes, containers
    nodes = {n.id: n for n in get_all_simul_nodes(n_nodes)}
    containers = {c.id: c for c in get_all_simul_containers(n_pods)}  

    # (5, 6) = (M, p) = (n_obj, #of divisions) -> H = C(M+p-1, p)
    ref_dirs = get_reference_directions("das-dennis", 5, n_partitions=6)
    algorithm = NSGA3(pop_size=212,
                    sampling=MySampling(),
                    selection=get_selection('tournament', func_comp=mybinary_tournament),
                    crossover=MyCrossover(),
                    mutation=MyMutation(),
                    eliminate_duplicates=MyDuplicateElimination(),
                    ref_dirs=ref_dirs)

    
    res = minimize(MyProblem(n_characters=len(containers)),
                algorithm,
                ('n_gen', 100),
                seed=1,
                save_history=True,
                return_least_infeasible=False,
                verbose=False)

    # Scatter(tight_layout=False, figsize=(15,25)).add(res.F, s=10).show()
    # results = res.X[np.argsort(res.F[:, 0])]
    # print(results)
    # print("Exec Time:", res.exec_time)    
    # record_generation_video(res)
    # return results[-1][0]
    
    ref_dirs = get_reference_directions("das-dennis", 5, n_partitions=6)
    F = res.F

    weights = np.array([0.15, 0.15, 0.15, 0.4, 0.15])
    a, _ = PseudoWeights(weights).do(F, return_pseudo_weights=True)
    return res.X[a][0]

       
if __name__ == '__main__':
    for_test(5, 6)