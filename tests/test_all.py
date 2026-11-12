"""
Run with:  python -m pytest -q

The first tests are the worked examples from ReliefLink Technical Context v2
(T1, T8, T20). If these pass, our formulas match the spec exactly.
The rest check that the quantum mapping is mathematically correct.
"""

import itertools
import numpy as np
import pytest

from relieflink_surge import spec
from relieflink_surge.scenario import default_scenario
from relieflink_surge.model import build_problem, to_ising
from relieflink_surge import baselines as B
from relieflink_surge.qaoa import build_hamiltonian, run_qaoa
from relieflink_surge.roads import build_town, closed_edges, road_route, open_network


# ---------- spec oracles ----------

def test_T1_priority_table():
    got = [spec.priority("medical", 5, True, 3, 10),
           spec.priority("rescue", 5, False, 6, 5),
           spec.priority("shelter", 3, False, 4, 45),
           spec.priority("food_water", 2, False, 10, 60),
           spec.priority("info", 2, False, 1, 5)]
    assert [round(g, 1) for g in got] == [129.2, 104.6, 36.0, 34.6, 2.3]
    assert got == sorted(got, reverse=True)          # order A, B, C, D, E


def test_T20_late_delivery():
    assert spec.priority("rescue", 4, False, 2, 40) == pytest.approx(80.0)


def test_T8_scoring_examples():
    a = spec.match_score(14, True, True, 0.8, 0, "fresh")
    b = spec.match_score(5, False, True, 0.9, 1, "fresh")
    c = spec.match_score(14, True, True, 0.6, 0, "fresh")
    a_stale = spec.match_score(14, True, True, 0.8, 0, "stale")
    assert round(a, 3) == 0.547 and round(b, 3) == 0.302
    assert round(c, 3) == 0.517 and round(a_stale, 3) == 0.447


# ---------- model / mapping ----------

@pytest.fixture(scope="module")
def prob():
    return build_problem(default_scenario())


def test_instance_size(prob):
    assert prob.n == 15
    assert len(prob.closed) > 0                       # flood closes roads


def test_flood_forces_detour():
    """Spec T5: a closed bridge makes the road route longer than without the flood."""
    sc = default_scenario()
    G = sc.town
    _, km_dry = road_route(G, (2, 4), (7, 4))
    _, km_flood = road_route(open_network(G, sc.flood_polygons), (2, 4), (7, 4))
    assert km_flood > km_dry


def test_hard_skill_filter(prob):
    """Medical needs first_aid, rescue needs swimming: no variable breaks this."""
    sc = prob.scenario
    for i, j in prob.variables:
        need = {"medical": "first_aid", "rescue": "swimming"}.get(sc.requests[j].req_type)
        assert need is None or need in sc.volunteers[i].skills


def test_ising_matches_qubo_on_every_bitstring(prob):
    """f(x) must equal offset + h.z + sum J z z for all 2^n inputs."""
    h, J, offset = to_ising(prob)
    X, costs = prob.all_costs()
    Z = 1 - 2 * X
    e = offset + Z @ h
    for (a, b), v in J.items():
        e = e + v * Z[:, a] * Z[:, b]
    assert np.allclose(e, costs)


def test_hamiltonian_diagonal_matches_costs(prob):
    """The Qiskit operator's diagonal (rescaled) equals our cost table."""
    H, _, _, offset, scale = build_hamiltonian(prob)
    diag = np.real(H.to_matrix(sparse=True).diagonal()) * scale + offset
    _, costs = prob.all_costs()
    assert np.allclose(diag, costs)


def test_penalty_makes_optimum_feasible(prob):
    x, _ = B.brute_force(prob)
    assert prob.is_feasible(x)


def test_story_greedy_lt_hungarian_lt_exact(prob):
    g = prob.value(B.greedy(prob))
    h = prob.value(B.hungarian(prob))
    e = prob.value(B.brute_force(prob)[0])
    assert g < h < e


def test_qaoa_runs_and_beats_random(prob):
    r = run_qaoa(prob, p=1, objective="cvar", maxiter=60)
    assert r["num_qubits"] == 15
    x_opt, k = B.brute_force(prob)
    assert r["exact_probs"][k] > 1 / 2 ** prob.n     # better than uniform
