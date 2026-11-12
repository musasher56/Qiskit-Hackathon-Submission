"""
QAOA (Quantum Approximate Optimization Algorithm), written by hand in Qiskit.

Circuit for depth p (one "layer" = cost step + mixer step):

    |0...0>  --H on every qubit-->  equal superposition of all 2^n bitstrings
    repeat p times:
        cost step   exp(-i * gamma_k * H_C)   built from our Ising terms
                      h_i Z_i      -> RZ(2 * gamma * h_i)       on qubit i
                      J_ab Z_a Z_b -> RZZ(2 * gamma * J_ab)     on qubits a,b
        mixer step  exp(-i * beta_k * sum X_i)
                      -> RX(2 * beta) on every qubit
    measure

A classical optimiser (COBYLA from SciPy) tunes the 2p angles. We grow the
circuit one layer at a time: depth 1 starts from a coarse grid search, and
each deeper circuit starts from the previous optimum stretched with INTERP
(Zhou et al., PRX 10, 021067, 2020).

Two training objectives:
  "standard" - minimise the expected energy <H_C> (Farhi et al., 2014).
               Evaluated with Qiskit's StatevectorEstimator.
  "cvar"     - minimise the average energy of only the best alpha fraction
               of outcomes (CVaR, Barkoutsos et al., Quantum 4, 256 (2020)).
               This rewards the circuit for making good answers likely,
               instead of making the *average* answer good.

Final answers always come from measured shots (StatevectorSampler), the same
way you would read a real device.

Simulation note: everything runs on an exact statevector simulator. No noise,
no real hardware. For training the CVaR objective we read the exact outcome
probabilities from the statevector (fine at <= 14 qubits, impossible on real
hardware, where we would estimate it from shots instead).
"""

import time
import numpy as np
from scipy.optimize import minimize
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import SparsePauliOp, Statevector
from qiskit.primitives import StatevectorEstimator, StatevectorSampler

from .model import to_ising


def build_hamiltonian(problem):
    """Ising terms -> Qiskit SparsePauliOp (qubit q = variable q).
    We divide by the largest coefficient so angle ranges stay sensible;
    this rescales energies but does not change which bitstring is best."""
    h, J, offset = to_ising(problem)
    terms = [("Z", [i], h[i]) for i in range(problem.n) if abs(h[i]) > 1e-12]
    terms += [("ZZ", [a, b], v) for (a, b), v in J.items()]
    H = SparsePauliOp.from_sparse_list(terms, num_qubits=problem.n)
    scale = float(np.max(np.abs(H.coeffs)))
    return H / scale, h / scale, {k: v / scale for k, v in J.items()}, offset, scale


def build_circuit(n, h, J, p):
    gammas = ParameterVector("gamma", p)
    betas = ParameterVector("beta", p)
    qc = QuantumCircuit(n)
    qc.h(range(n))
    for k in range(p):
        for i in range(n):
            if abs(h[i]) > 1e-12:
                qc.rz(2 * gammas[k] * h[i], i)
        for (a, b), v in J.items():
            qc.rzz(2 * gammas[k] * v, a, b)
        qc.rx(2 * betas[k], range(n))
    return qc, list(gammas) + list(betas)


def _interp(theta, p_old):
    """INTERP (Zhou et al., PRX 10, 021067, 2020): stretch the best depth-p
    angles into a starting point for depth p+1."""
    q = p_old
    def ext(v):
        v = np.concatenate([[0.0], v, [0.0]])
        return np.array([((i - 1) / q) * v[i - 1] + ((q - i + 1) / q) * v[i] for i in range(1, q + 2)])
    return np.concatenate([ext(theta[:q]), ext(theta[q:])])


def train_layerwise(problem, max_p=5, objective="cvar", alpha=0.1, maxiter=300,
                    shots=4096, seed=7, grid=(12, 10)):
    """Train depth 1, 2, ..., max_p in turn.

    Depth 1 starts from the best point of a coarse (gamma, beta) grid.
    Each deeper circuit starts from the previous depth's optimum, stretched
    with INTERP, then COBYLA refines it. Returns one result per depth."""
    H, h, J, offset, scale = build_hamiltonian(problem)
    X, costs = problem.all_costs()
    sorted_idx = np.argsort(costs)
    c_sorted = costs[sorted_idx]
    estimator = StatevectorEstimator()
    results, prev, t0 = [], None, time.time()

    for p in range(1, max_p + 1):
        qc, params = build_circuit(problem.n, h, J, p)
        circuit_params = list(qc.parameters)
        order = [circuit_params.index(par) for par in params]
        evals = {"n": 0}

        def bind_values(theta, order=order):
            vals = np.empty(len(theta))
            vals[order] = theta
            return vals

        def probs(theta, qc=qc, bind_values=bind_values):
            sv = Statevector(qc.assign_parameters(bind_values(theta)))
            return np.abs(sv.data) ** 2           # index k <-> bit q of k = qubit q

        def f_standard(theta, qc=qc, bind_values=bind_values, evals=evals):
            evals["n"] += 1
            res = estimator.run([(qc, H, bind_values(theta))]).result()
            return float(res[0].data.evs)

        def f_cvar(theta, probs=probs, evals=evals):
            evals["n"] += 1
            pr = probs(theta)[sorted_idx]
            cum = np.cumsum(pr)
            k = int(np.searchsorted(cum, alpha))
            tail = np.sum(pr[:k] * c_sorted[:k]) + (alpha - (cum[k - 1] if k else 0.0)) * c_sorted[k]
            return float(tail / alpha) / scale

        f = f_cvar if objective == "cvar" else f_standard
        if prev is None:
            gs = np.linspace(0.05, 2.0, grid[0])
            bs = np.linspace(0.05, 1.5, grid[1])
            _, g0, b0 = min((f(np.array([g, b])), g, b) for g in gs for b in bs)
            x0 = np.array([g0, b0])
        else:
            x0 = _interp(prev, p - 1)
        r = minimize(f, x0, method="COBYLA", options={"maxiter": maxiter})
        prev = r.x

        meas = qc.assign_parameters(bind_values(r.x))
        meas.measure_all()
        counts = StatevectorSampler(seed=seed).run([meas], shots=shots).result()[0].data.meas.get_counts()
        results.append({
            "p": p, "objective": objective, "alpha": alpha,
            "theta": r.x.tolist(), "train_fun": float(r.fun),
            "evals": evals["n"], "seconds": time.time() - t0,
            "counts": counts, "to_x": _to_x,
            "exact_probs": probs(r.x), "circuit": qc, "num_qubits": problem.n,
            "depth": meas.decompose().depth(),
            "two_qubit_gates": sum(1 for ins in meas.data if ins.operation.name == "rzz"),
        })
    return results


def run_qaoa(problem, p=2, objective="cvar", **kw):
    """Convenience wrapper: train layer by layer up to depth p, return depth p."""
    return train_layerwise(problem, max_p=p, objective=objective, **kw)[-1]


def _to_x(bitstring):
    """Qiskit bitstrings are little-endian: rightmost char = qubit 0."""
    return np.array([int(c) for c in bitstring[::-1]], dtype=int)


def analyse(problem, result, optimum_value):
    """Turn shot counts into the numbers we report."""
    counts, to_x = result["counts"], result["to_x"]
    shots = sum(counts.values())
    feas_shots = opt_shots = 0
    best_x, best_v = None, -np.inf
    for bs, c in counts.items():
        x = to_x(bs)
        if problem.is_feasible(x):
            feas_shots += c
            v = problem.value(x)
            if v > best_v:
                best_v, best_x = v, x
            if abs(v - optimum_value) < 1e-9:
                opt_shots += c
    top_bs = max(counts, key=counts.get)
    top_x = to_x(top_bs)
    feas_sorted = sorted(((c, bs) for bs, c in counts.items()
                          if problem.is_feasible(to_x(bs))), reverse=True)
    top_feas_x = to_x(feas_sorted[0][1]) if feas_sorted else None
    good90 = sum(c for bs, c in counts.items()
                 if problem.is_feasible(to_x(bs)) and problem.value(to_x(bs)) >= 0.9 * optimum_value)
    return {
        "p_good90": good90 / shots,
        "p_feasible": feas_shots / shots,
        "p_optimal": opt_shots / shots,
        "p_optimal_random": 1 / 2 ** problem.n,
        "most_frequent": {
            "assignment": problem.assignment(top_x),
            "feasible": bool(problem.is_feasible(top_x)),
            "value": float(problem.value(top_x)),
            "is_optimal": bool(problem.is_feasible(top_x)
                               and abs(problem.value(top_x) - optimum_value) < 1e-9),
            "share": counts[top_bs] / shots,
        },
        "most_frequent_feasible_ratio": (float(problem.value(top_feas_x)) / optimum_value
                                         if top_feas_x is not None else 0.0),
        "best_sampled_ratio": (best_v / optimum_value) if best_x is not None else 0.0,
        "best_sampled_assignment": problem.assignment(best_x) if best_x is not None else [],
    }
