"""
The optimisation model: joint assignment of volunteers to a surge of requests,
written as a QUBO (Quadratic Unconstrained Binary Optimisation).

Decision variables
    x_a in {0,1} for every usable (volunteer i, request j) pair a = (i, j).
    A pair is removed before the quantum step, so it never costs a qubit, if
      - flood-closed roads leave no route at all (spec T6),
      - the volunteer lacks a skill the request needs (hard skill filter), or
      - the road ETA is beyond the search limit, or
      - the volunteer is not among the request's top-k candidates by score
        (spec §8 Stage 4 notifies only the top 3-5).

Objective (we MINIMISE the QUBO cost f; the "relief value" we report is -f)
    f(x) = - sum_a  w_a x_a                       (reward for serving)
           + sum_{a<b} Q_ab x_a x_b               (pairwise terms)

    w_a  = priority_j * score_ij        (spec §7 x spec §8, workload 0)

Pairwise terms Q_ab
    1. Same request, two volunteers  -> P (spec §6.2: one assigned lead).
    2. Same volunteer, two requests:
         if the leg between the two requests is short and not flooded
             -> chain cost c >= 0 (our extension, see chain_cost)
         else
             -> P (impossible trip).

P (penalty) is set above the largest single reward, which guarantees that the
lowest-cost bitstring never breaks a rule: dropping any variable that causes
a violation always lowers the cost (proof sketch in the report).
"""

from dataclasses import dataclass, field
import itertools
import numpy as np

from . import spec
from .roads import open_network, road_route, closed_edges


@dataclass
class Problem:
    scenario: object
    variables: list          # list of (volunteer_index, request_index)
    w: np.ndarray            # linear rewards, length n
    Q: np.ndarray            # upper-triangular pairwise costs, n x n
    Q_kind: dict             # (a,b) -> "one_lead" | "bad_chain" | "chain"
    penalty: float
    eta: dict                # (i,j) -> ETA minutes (usable pairs only)
    blocked: list            # (i,j) pairs with no open road route
    pruned: dict             # reason -> list of (i,j) pairs removed
    priorities: list         # per request
    routes: dict = None      # (i,j) -> list of road nodes
    legs: dict = None        # (j,k) -> list of road nodes between two requests
    closed: set = None       # closed road segments

    @property
    def n(self):
        return len(self.variables)

    # ----- cost / decoding -----
    def cost(self, x):
        x = np.asarray(x, dtype=float)
        return float(-self.w @ x + x @ self.Q @ x)

    def value(self, x):
        """Relief value (higher is better) = -cost."""
        return -self.cost(x)

    def assignment(self, x):
        """Readable list of (volunteer_id, request_id)."""
        sc = self.scenario
        return [(sc.volunteers[i].vid, sc.requests[j].rid)
                for (i, j), on in zip(self.variables, x) if on]

    def violations(self, x):
        """Count broken rules: two leads on one request, impossible chains,
        or more than two requests for one volunteer."""
        bad = 0
        for (a, b), kind in self.Q_kind.items():
            if kind in ("one_lead", "bad_chain") and x[a] and x[b]:
                bad += 1
        per_vol = {}
        for (i, _), on in zip(self.variables, x):
            if on:
                per_vol[i] = per_vol.get(i, 0) + 1
        bad += sum(1 for c in per_vol.values() if c > 2)
        return bad

    def is_feasible(self, x):
        return self.violations(x) == 0

    def all_costs(self):
        """Cost of every one of the 2^n bitstrings, index k <-> bits of k
        (bit q of k = variable q). Used for brute force and analysis."""
        n = self.n
        k = np.arange(2 ** n)
        X = ((k[:, None] >> np.arange(n)) & 1).astype(float)
        lin = -(X @ self.w)
        quad = np.einsum("ki,ij,kj->k", X, self.Q, X)
        return X, lin + quad


def pair_weight(sc, i, j, eta_min, workload=0):
    """priority_j * spec score for volunteer i on request j."""
    v, r = sc.volunteers[i], sc.requests[j]
    need = spec.REQUIRED_SKILL.get(r.req_type)
    skill_ok = need is None or need in v.skills
    tier = spec.freshness_tier(v.minutes_since_seen)
    p = spec.priority(r.req_type, r.urgency, r.vulnerable, r.people, r.wait_minutes)
    # Equipment: the spec does not say which request types need equipment,
    # so we treat equipment as "not needed" (equipment_match = 1) everywhere.
    s = spec.match_score(eta_min, skill_ok, True, v.trust, workload, tier)
    return p * s


def chain_cost(sc, i, j, k, eta, leg_lengths):
    """Our extension: volunteer i serves j and k in one trip.

    The spec's triage order says the higher-priority request goes first.
    The second request's ETA becomes ETA(i->first) + ETA(first->second),
    and the volunteer now holds a task, so workload = 1 (spec §8 term).

    chain cost = (w_first + w_second served separately) - (value of the trip)
    which is >= 0 by the triangle inequality, so chaining is never free."""
    v = sc.volunteers[i]
    pj = spec.priority(*_prio_args(sc.requests[j]))
    pk = spec.priority(*_prio_args(sc.requests[k]))
    first, second = (j, k) if pj >= pk else (k, j)
    leg_km = leg_lengths[tuple(sorted((first, second)))]
    leg_eta = road_eta_minutes(leg_km, v.transport)
    trip_value = (pair_weight(sc, i, first, eta[(i, first)], workload=0)
                  + pair_weight(sc, i, second, eta[(i, first)] + leg_eta, workload=1))
    separate = (pair_weight(sc, i, first, eta[(i, first)])
                + pair_weight(sc, i, second, eta[(i, second)]))
    return separate - trip_value


def road_eta_minutes(km, transport):
    """Road route length / assumed flood speed (spec §8 Stage 2 speeds).
    No 1.5 detour factor: the route already follows the roads."""
    return km / spec.SPEED_KMH[transport] * 60.0


def _prio_args(r):
    return (r.req_type, r.urgency, r.vulnerable, r.people, r.wait_minutes)


def build_problem(sc, penalty_factor=1.5, allow_chaining=True):
    """Turn a scenario into a QUBO. penalty = penalty_factor * max reward."""
    H = open_network(sc.town, sc.flood_polygons)
    closed = closed_edges(sc.town, sc.flood_polygons)
    eta, routes, variables = {}, {}, []
    pruned = {"no_road": [], "skill": [], "too_far": [], "not_top_k": []}
    for i, v in enumerate(sc.volunteers):
        for j, r in enumerate(sc.requests):
            need = spec.REQUIRED_SKILL.get(r.req_type)
            if sc.hard_skill_filter and need and need not in v.skills:
                pruned["skill"].append((i, j))
                continue
            path, km = road_route(H, (v.x, v.y), (r.x, r.y))
            if path is None:
                pruned["no_road"].append((i, j))
                continue
            t = road_eta_minutes(km, v.transport)
            if t > sc.max_eta_minutes:
                pruned["too_far"].append((i, j))
                continue
            eta[(i, j)], routes[(i, j)] = t, path
            variables.append((i, j))

    # keep only each request's top-k candidates by spec score
    keep = []
    for j in range(len(sc.requests)):
        cands = sorted([(pair_weight(sc, i, jj, eta[(i, jj)]), i) for i, jj in variables if jj == j],
                       reverse=True)
        keep += [(i, j) for _, i in cands[:sc.top_k]]
        pruned["not_top_k"] += [(i, j) for _, i in cands[sc.top_k:]]
    variables = sorted(keep)

    # road legs between pairs of requests (for chaining)
    legs, leg_len = {}, {}
    for j in range(len(sc.requests)):
        for k in range(j + 1, len(sc.requests)):
            a, b = sc.requests[j], sc.requests[k]
            path, km = road_route(H, (a.x, a.y), (b.x, b.y))
            legs[(j, k)], leg_len[(j, k)] = path, (km if km is not None else float("inf"))

    n = len(variables)
    w = np.array([pair_weight(sc, i, j, eta[(i, j)]) for i, j in variables])
    P = penalty_factor * float(w.max())
    Q = np.zeros((n, n))
    kind = {}
    for a, b in itertools.combinations(range(n), 2):
        (ia, ja), (ib, jb) = variables[a], variables[b]
        if ja == jb:                                   # same request
            Q[a, b], kind[(a, b)] = P, "one_lead"
        elif ia == ib:                                 # same volunteer
            ok = allow_chaining and leg_len[tuple(sorted((ja, jb)))] <= sc.max_chain_leg_km
            if ok:
                Q[a, b], kind[(a, b)] = chain_cost(sc, ia, ja, jb, eta, leg_len), "chain"
            else:
                Q[a, b], kind[(a, b)] = P, "bad_chain"

    prios = [spec.priority(*_prio_args(r)) for r in sc.requests]
    return Problem(sc, variables, w, Q, kind, P, eta, pruned["no_road"], pruned, prios,
                   routes, legs, closed)


def to_ising(problem):
    """QUBO -> Ising, using x = (1 - z) / 2 with z in {+1, -1}.

    f(x) = offset + sum_i h_i z_i + sum_{a<b} J_ab z_a z_b

      linear  l x      = l/2 - (l/2) z
      pair    Q x_a x_b = Q/4 (1 - z_a - z_b + z_a z_b)

    z = +1 means qubit |0> (variable off), z = -1 means |1> (variable on).
    """
    n = problem.n
    lin = -problem.w
    h = np.zeros(n)
    J = {}
    offset = 0.0
    for a in range(n):
        offset += lin[a] / 2
        h[a] += -lin[a] / 2
    for a in range(n):
        for b in range(a + 1, n):
            q = problem.Q[a, b]
            if q == 0:
                continue
            offset += q / 4
            h[a] -= q / 4
            h[b] -= q / 4
            J[(a, b)] = q / 4
    return h, J, offset
