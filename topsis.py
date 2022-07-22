# https://github.com/django2302/kubernetes_scheduler/blob/master/topsisWithoutPrint.py

import numpy as np
import math


def normalisation(data):
    sqr_mtrx = np.square(data)
    sum_matrx = np.sum(sqr_mtrx, axis=0)
    sq_root = np.sqrt(sum_matrx)
    sq_root = np.around(sq_root, decimals=2)
    divide_array = np.divide(data, sq_root)

    return divide_array

def weigh_norm(Normal_array, weight):
    weighted = Normal_array * weight
    
    return weighted

def ideal_best(data):
    best = []
    best = np.amax(data, axis=0)

    return best

def ideal_worst(data):
    worst = []
    worst = np.amin(data, axis=0)

    return worst

def euclidian_best(data, id_best):
    n, m = len(data), len(data[0])
    euc_best = []
    tmp = 0
    for i in range(n):
        for j in range(m):
            tmp = tmp + (data[i][j]-id_best[j])**2
        tmp = math.sqrt(tmp)
        euc_best.append(tmp)

    return euc_best

def euclidian_worst(data, id_worst):
    n, m = len(data), len(data[0])
    euc_worst = []
    tmp = 0
    for i in range(n):
        for j in range(m):
            tmp = tmp + (data[i][j]-id_worst[j])**2
        tmp = math.sqrt(tmp)
        euc_worst.append(tmp)

    return euc_worst

def performance_score (id_best, id_worst):
    n = len(id_best)
    per_score = []
    tmp = 0
    for i in range(n):
        tmp = id_worst[i]/(id_best[i] + id_worst[i])
        per_score.append(tmp)

    return per_score
       
def best_host(system_values): # input: {'name':{'memory':float , 'disk':flaot} ...}

    vals = []
    for metrs in system_values.values():
        vals.append([metrs['cpu_core'], metrs['memory'], metrs['disk_total'], metrs['disk_free'], metrs['bitrate']])

    data = np.array(vals)

    weight =  [40, 20, 10, 15, 40]
    
    normal_array = normalisation(data)
    weight_normal_array  = weigh_norm(normal_array, weight)
    best_array = ideal_best(weight_normal_array) 
    worst_array = ideal_worst(weight_normal_array)
    euc_best = euclidian_best(weight_normal_array, best_array)
    euc_worst = euclidian_worst(weight_normal_array, worst_array)
    per_score = performance_score(euc_best , euc_worst)
    best_alternate = per_score.index(max(per_score))

    return list(system_values)[best_alternate]