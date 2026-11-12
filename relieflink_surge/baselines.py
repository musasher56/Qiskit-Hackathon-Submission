"""
Classical reference methods.

1. greedy      - what ReliefLink does today (spec §8 Stage 4): handle requests
                 one at a time in priority order; each takes its best-scoring
                 volunteer who is still free. One task per volunteer.
2. hungarian   - the provably optimal answer when every volunteer may take at
                 most ONE request (a linear assignment problem). Solved exactly
                 in polynomial time by SciPy's linear_sum_assignment.
                 It cannot represent our two-requests-per-trip extension,
                 because that needs pairwise (quadratic) terms.
3. brute force - tries all 2^n bitstrings of the full QUBO. Exact, but the
                 work doubles with every extra variable.
4. random      - uniform random bitstrings with the same shot budget as QAOA;
                 shows what "no algorithm at all" achieves.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment


def _x_from_pairs(problem, pairs):
    x = np.zeros(problem.n, dtype=int)
    for a, (i, j) in enumerate(problem.variables):
        if (i, j) in pairs:
            x[a] = 1
    return x


def greedy(problem):
    order = sorted(range(len(problem.scenario.requests)),
                   key=lambda j: -problem.priorities[j])
    used, chosen = set(), set()
    for j in order:
        options = [(problem.w[a], i) for a, (i, jj) in enumerate(problem.variables)
                   if jj == j and i not in used]
        if options:
            _, i = max(options)
            used.add(i)
            chosen.add((i, j))
    return _x_from_pairs(problem, chosen)


def hungarian(problem):
    nv = len(problem.scenario.volunteers)
    nr = len(problem.scenario.requests)
    M = np.zeros((nv, nr))           # 0 reward for blocked pairs
    for a, (i, j) in enumerate(problem.variables):
        M[i, j] = problem.w[a]
    rows, cols = linear_sum_assignment(-M)
    chosen = {(i, j) for i, j in zip(rows, cols) if M[i, j] > 0}
    return _x_from_pairs(problem, chosen)


def brute_force(problem):
    X, costs = problem.all_costs()
    k = int(np.argmin(costs))
    return X[k].astype(int), k


def random_sampling(problem, shots, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 2, size=(shots, problem.n))
    feas = [x for x in X if problem.is_feasible(x)]
    best = max(feas, key=problem.value) if feas else None
    return {
        "p_feasible": len(feas) / shots,
        "p_optimal_theoretical": 1 / 2 ** problem.n,
        "best_x": None if best is None else best.astype(int),
    }
