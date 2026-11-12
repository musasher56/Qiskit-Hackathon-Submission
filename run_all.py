"""
Reproduce every number and chart in the report:

    python run_all.py            # full run (about 6-8 minutes on a laptop)
    python run_all.py --quick    # skip the penalty sweep and scaling study (about 3 minutes)

Outputs go to results/ : results.json, summary.md and the PNG charts.
All randomness is seeded, so repeated runs give the same numbers.
"""

import argparse
import json
import os
import time

import numpy as np

from relieflink_surge.scenario import default_scenario, random_scenario
from relieflink_surge.model import build_problem
from relieflink_surge import baselines as B
from relieflink_surge.qaoa import train_layerwise, analyse
from relieflink_surge import plots

OUT = "results"
SEED = 7


def fmt_assign(a):
    return ", ".join(f"{v}->{r}" for v, r in a) or "(none)"


def main(quick=False):
    os.makedirs(OUT, exist_ok=True)
    t_start = time.time()
    sc = default_scenario()
    prob = build_problem(sc)
    report = {"scenario": {}, "baselines": {}, "qaoa": {}, "sweeps": {}}

    # ---------------- problem summary ----------------
    report["scenario"] = {
        "qubits": prob.n,
        "requests": [{"id": r.rid, "label": r.label, "priority": round(p, 2)}
                     for r, p in zip(sc.requests, prob.priorities)],
        "volunteers": [{"id": v.vid, "label": v.label} for v in sc.volunteers],
        "removed_by_flood": [(sc.volunteers[i].vid, sc.requests[j].rid) for i, j in prob.blocked],
        "pruned": {k: [(sc.volunteers[i].vid, sc.requests[j].rid) for i, j in v] for k, v in prob.pruned.items()},
        "closed_road_segments": len(prob.closed),
        "variables": [(sc.volunteers[i].vid, sc.requests[j].rid, round(prob.eta[(i, j)], 1),
                       round(float(prob.w[a]), 2)) for a, (i, j) in enumerate(prob.variables)],
        "penalty": round(prob.penalty, 2),
    }
    print(f"Qubits: {prob.n}  pruned: { {k: len(v) for k, v in prob.pruned.items()} }  closed roads: {len(prob.closed)}")

    # ---------------- classical baselines ----------------
    t = time.time(); x_exact, _ = B.brute_force(prob); t_bf = time.time() - t
    opt = prob.value(x_exact)
    x_greedy, x_hung = B.greedy(prob), B.hungarian(prob)
    for name, x in [("greedy", x_greedy), ("hungarian", x_hung), ("exact", x_exact)]:
        report["baselines"][name] = {"assignment": prob.assignment(x), "value": round(prob.value(x), 2),
                                     "ratio": round(prob.value(x) / opt, 4),
                                     "feasible": bool(prob.is_feasible(x))}
        print(f"{name:10s} {prob.value(x):7.2f} ({100 * prob.value(x) / opt:5.1f}%)  {fmt_assign(prob.assignment(x))}")
    report["baselines"]["exact"]["seconds"] = round(t_bf, 4)
    rnd = B.random_sampling(prob, 4096, seed=SEED)
    report["baselines"]["random"] = {"p_feasible": round(rnd["p_feasible"], 4),
                                     "p_optimal": rnd["p_optimal_theoretical"]}

    # ---------------- QAOA: grow depth 1..MAX_P, both objectives ----------------
    MAX_P = 5
    sweep = {"standard": [], "cvar": []}
    runs = {}
    for obj in ["cvar", "standard"]:
        for r in train_layerwise(prob, max_p=MAX_P, objective=obj, seed=SEED):
            p = r["p"]
            a = analyse(prob, r, opt)
            runs[(obj, p)] = (r, a)
            sweep[obj].append((p, a["p_optimal"], a["p_feasible"], a["most_frequent_feasible_ratio"]))
            report["qaoa"][f"{obj}_p{p}"] = {
                "seconds_cumulative": round(r["seconds"], 2), "optimizer_evals": r["evals"],
                "circuit_depth": r["depth"], "rzz_gates": r["two_qubit_gates"],
                **{k: (round(v, 5) if isinstance(v, float) else v) for k, v in a.items()},
            }
            mf = a["most_frequent"]
            print(f"QAOA {obj:8s} p={p}: P(valid)={a['p_feasible']:.2f} P(opt)={a['p_optimal']:.4f} "
                  f"P(>=90%)={a['p_good90']:.3f} most-frequent-valid={100 * a['most_frequent_feasible_ratio']:.0f}%  "
                  f"top={fmt_assign(mf['assignment'])} ({r['seconds']:.0f}s)")

    # "headline" quantum run used in the figures and app: best CVaR depth
    head_key = max((k for k in runs if k[0] == "cvar"),
                   key=lambda k: (runs[k][1]["most_frequent_feasible_ratio"], runs[k][1]["p_optimal"]))
    head_r, head_a = runs[head_key]
    report["headline_run"] = f"{head_key[0]}_p{head_key[1]}"
    x_head = head_r["to_x"](max(
        (bs for bs in head_r["counts"] if prob.is_feasible(head_r["to_x"](bs))),
        key=lambda bs: head_r["counts"][bs]))
    best_std = max((runs[k] for k in runs if k[0] == "standard"),
                   key=lambda ra: (ra[1]["most_frequent_feasible_ratio"], ra[1]["p_optimal"]))

    # ---------------- penalty sweep (CVaR, p=2) ----------------
    pen_rows = []
    for factor in ([] if quick else [1.1, 1.5, 3.0, 6.0]):
        pf = build_problem(sc, penalty_factor=factor)
        r = train_layerwise(pf, max_p=3, objective="cvar", seed=SEED)[-1]
        a = analyse(pf, r, opt)
        pen_rows.append((factor, a["p_feasible"], a["p_optimal"]))
        print(f"penalty x{factor}: P(valid)={a['p_feasible']:.2f} P(opt)={a['p_optimal']:.3f}")
    report["sweeps"]["penalty"] = [{"factor": f, "p_feasible": round(a, 4), "p_optimal": round(b, 4)}
                                   for f, a, b in pen_rows]

    # ---------------- scaling study ----------------
    scale_rows = []
    if not quick:
        for nv, nr in [(2, 3), (3, 3), (3, 4), (4, 4), (4, 5), (5, 5)]:
            for s in range(2):
                pr = build_problem(random_scenario(nv, nr, seed=100 + 10 * nv + s))
                if pr.n < 4 or pr.n > 15:
                    continue
                xo, _ = B.brute_force(pr)
                o = pr.value(xo)
                if o <= 0:
                    continue
                r = train_layerwise(pr, max_p=3, objective="cvar", seed=SEED)[-1]
                a = analyse(pr, r, o)
                scale_rows.append((pr.n, a["p_optimal"], 1 / 2 ** pr.n, r["seconds"]))
                print(f"scaling: {pr.n} qubits -> P(opt)={a['p_optimal']:.3f} vs random {1 / 2 ** pr.n:.4f}")
        report["sweeps"]["scaling"] = [{"qubits": q, "p_optimal": round(p, 4), "p_random": r_, "seconds": round(t_, 2)}
                                       for q, p, r_, t_ in scale_rows]

    # ---------------- figures ----------------
    plots.scenario_only(prob, f"{OUT}/scenario.png")
    plots.map_panels(prob, [
        (f"ReliefLink greedy today: {prob.value(x_greedy):.1f} ({100 * prob.value(x_greedy) / opt:.0f}%)", x_greedy),
        (f"Hungarian, 1 task each: {prob.value(x_hung):.1f} ({100 * prob.value(x_hung) / opt:.0f}%)", x_hung),
        (f"QAOA most frequent valid: {prob.value(x_head):.1f} ({100 * prob.value(x_head) / opt:.0f}%)", x_head),
        (f"Exact optimum: {opt:.1f} (100%)", x_exact),
    ], f"{OUT}/assignments.png")
    plots.method_bars([
        ("Greedy (ReliefLink today)", prob.value(x_greedy), False),
        ("Hungarian (1 task each)", prob.value(x_hung), False),
        (f"QAOA standard, p={best_std[0]['p']} (most frequent valid)",
         best_std[1]["most_frequent_feasible_ratio"] * opt, True),
        (f"QAOA {head_key[0]}, p={head_key[1]} (most frequent valid)",
         head_a["most_frequent_feasible_ratio"] * opt, True),
        ("Exact (brute force)", opt, False),
    ], opt, f"{OUT}/method_comparison.png")
    plots.distribution(prob, head_r["counts"], head_r["to_x"], opt, f"{OUT}/qaoa_distribution.png")
    plots.depth_sweep(sweep, 1 / 2 ** prob.n, f"{OUT}/depth_sweep.png")
    if pen_rows:
        plots.penalty_sweep(pen_rows, f"{OUT}/penalty_sweep.png")
    if scale_rows:
        plots.scaling(scale_rows, f"{OUT}/scaling.png")
    try:
        circ = runs[("cvar", 1)][0]["circuit"].copy()
        circ.draw("mpl", fold=-1, filename=f"{OUT}/qaoa_circuit_p1.png")
    except Exception as e:   # drawing needs pylatexenc; never fail the run for it
        print("circuit drawing skipped:", e)

    # ---------------- write results ----------------
    with open(f"{OUT}/results.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    with open(f"{OUT}/summary.md", "w") as f:
        f.write("| Method | Assignment | Relief value | % of optimum |\n|---|---|---|---|\n")
        for name, key in [("Greedy (ReliefLink today)", "greedy"), ("Hungarian (1 task each)", "hungarian"),
                          ("Exact (brute force)", "exact")]:
            b = report["baselines"][key]
            f.write(f"| {name} | {fmt_assign(b['assignment'])} | {b['value']:.2f} | {100 * b['ratio']:.1f}% |\n")
        f.write("\n| QAOA run | P(valid) | P(optimum) | P(>=90% of optimum) | Most frequent valid answer |\n|---|---|---|---|---|\n")
        for k, v in report["qaoa"].items():
            f.write(f"| {k} | {100 * v['p_feasible']:.1f}% | {100 * v['p_optimal']:.2f}% | {100 * v['p_good90']:.1f}% | "
                    f"{100 * v['most_frequent_feasible_ratio']:.1f}% of optimum |\n")
        f.write(f"\nRandom guessing: P(optimum) = 1/2^{prob.n} = {100 / 2 ** prob.n:.4f}%, "
                f"P(valid) = {100 * rnd['p_feasible']:.1f}%\n")
    print(f"\nDone in {time.time() - t_start:.0f}s. See {OUT}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the penalty sweep and scaling study")
    main(ap.parse_args().quick)
