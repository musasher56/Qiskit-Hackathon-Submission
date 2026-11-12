"""
Interactive demo:   streamlit run app.py

Shows the flood-surge scenario on a map, lets you run each method and see
which volunteer goes where, and shows what the quantum circuit actually
measured.
"""

import copy
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from relieflink_surge.scenario import default_scenario
from relieflink_surge.model import build_problem
from relieflink_surge import baselines as B
from relieflink_surge.qaoa import run_qaoa, analyse
from relieflink_surge import plots

st.set_page_config(page_title="ReliefLink Surge Optimizer", layout="wide")
st.title("ReliefLink Surge Optimizer")
st.caption("Joint volunteer assignment for a flood surge, solved with QAOA in Qiskit "
           "and checked against greedy, Hungarian and brute-force baselines.")

# ---------------- controls ----------------
with st.sidebar:
    st.header("Scenario")
    flood_on = st.checkbox("Flood zone active", value=True,
                           help="Turning it off reopens every road and bridge, so routes and travel times change.")
    chaining = st.checkbox("Allow two nearby requests per trip", value=True,
                           help="Our extension. Off = the classic one-task-per-volunteer problem.")
    st.header("QAOA")
    objective = st.radio("Training objective", ["cvar", "standard"],
                         format_func=lambda s: "CVaR (best 10% of outcomes)" if s == "cvar" else "Standard (average energy)")
    depth = st.select_slider("Depth p (layers)", options=[1, 2, 3, 4, 5], value=4,
                             help="Trained layer by layer; p=4 takes about a minute the first time.")
    penalty = st.select_slider("Penalty P (x largest reward)", options=[1.1, 1.5, 3.0, 6.0], value=1.5)
    run = st.button("Run QAOA", type="primary", width="stretch")


def make_problem(flood_on, chaining, penalty):
    sc = default_scenario()
    if not flood_on:
        sc = copy.deepcopy(sc)
        sc.flood_polygons = []
    return build_problem(sc, penalty_factor=penalty, allow_chaining=chaining)


def _in_big_stack_thread(fn, *args):
    """Streamlit runs scripts in a thread with a small stack; Qiskit 2.x's
    compiled circuit code can overflow it (segfault). Run the work in our own
    thread with a 256 MB stack instead."""
    import threading
    out = {}

    def target():
        try:
            out["v"] = fn(*args)
        except Exception as e:   # pass errors back to the page
            out["e"] = e
    old = threading.stack_size(256 * 1024 * 1024)
    try:
        t = threading.Thread(target=target)
        t.start()
    finally:
        threading.stack_size(old)
    t.join()
    if "e" in out:
        raise out["e"]
    return out["v"]


def _qaoa_job(flood_on, chaining, penalty, objective, depth):
    prob = make_problem(flood_on, chaining, penalty)
    x_opt, _ = B.brute_force(prob)
    opt = prob.value(x_opt)
    r = run_qaoa(prob, p=depth, objective=objective)
    a = analyse(prob, r, opt)
    return r["counts"], a, r["seconds"], r["depth"], r["two_qubit_gates"]


@st.cache_data(show_spinner=False)
def cached_qaoa(flood_on, chaining, penalty, objective, depth):
    return _in_big_stack_thread(_qaoa_job, flood_on, chaining, penalty, objective, depth)


prob = make_problem(flood_on, chaining, penalty)
sc = prob.scenario
x_exact, _ = B.brute_force(prob)
opt = prob.value(x_exact)
x_greedy, x_hung = B.greedy(prob), B.hungarian(prob)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Qubits (usable pairs)", prob.n)
c2.metric("Possible assignments", f"{2 ** prob.n:,}")
c3.metric("Road segments closed by flood", len(prob.closed))
c4.metric("Pairs removed before the circuit", sum(len(v) for v in prob.pruned.values()),
          help="No road route, missing required skill, too far, or not in the request's top 3")

# ---------------- QAOA ----------------
qaoa_x, qaoa_info = None, None
if run or st.session_state.get("ran"):
    st.session_state["ran"] = True
    with st.spinner("Training the circuit layer by layer and measuring 4,096 shots (about a minute at p=4)..."):
        counts, a, secs, cdepth, nrzz = cached_qaoa(flood_on, chaining, penalty, objective, depth)
    to_x = lambda bs: np.array([int(c) for c in bs[::-1]])
    valid = [bs for bs in counts if prob.is_feasible(to_x(bs))]
    if valid:
        qaoa_x = to_x(max(valid, key=counts.get))
    qaoa_info = (counts, a, secs, cdepth, nrzz, to_x)

# ---------------- map + table ----------------
left, right = st.columns([3, 2])
with left:
    choice = st.radio("Show on map", ["Greedy (ReliefLink today)", "Hungarian (1 task each)",
                                      "QAOA (most frequent valid)", "Exact optimum"],
                      horizontal=True, index=3 if qaoa_x is None else 2)
    x_show = {"Greedy (ReliefLink today)": x_greedy, "Hungarian (1 task each)": x_hung,
              "QAOA (most frequent valid)": qaoa_x, "Exact optimum": x_exact}[choice]
    fig, ax = plt.subplots(figsize=(8, 5.6))
    plots.draw_map(ax, prob, x_show,
                   "Run QAOA in the sidebar first" if x_show is None else
                   f"{choice}: {prob.value(x_show):.1f} ({100 * prob.value(x_show) / opt:.0f}% of optimum)")
    st.pyplot(fig)
    plt.close(fig)

with right:
    rows = [("Greedy (ReliefLink today)", x_greedy), ("Hungarian (1 task each)", x_hung)]
    if qaoa_x is not None:
        rows.append((f"QAOA {objective}, p={depth}", qaoa_x))
    rows.append(("Exact (brute force)", x_exact))
    st.subheader("Results")
    st.dataframe(pd.DataFrame([{
        "Method": n,
        "Assignment": ", ".join(f"{v}->{r}" for v, r in prob.assignment(x)) or "(none)",
        "Relief value": round(prob.value(x), 1),
        "% of optimum": f"{100 * prob.value(x) / opt:.0f}%",
    } for n, x in rows]), hide_index=True, width="stretch")
    with st.expander("Volunteers and requests"):
        st.dataframe(pd.DataFrame(
            [{"ID": v.vid, "Who": v.label} for v in sc.volunteers]
            + [{"ID": r.rid, "Who": f"{r.label} (priority {p:.1f})"} for r, p in zip(sc.requests, prob.priorities)]),
            hide_index=True, width="stretch")

# ---------------- what the circuit measured ----------------
if qaoa_info:
    counts, a, secs, cdepth, nrzz, to_x = qaoa_info
    st.subheader("What the quantum circuit measured")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P(valid answer)", f"{100 * a['p_feasible']:.1f}%")
    m2.metric("P(exact optimum)", f"{100 * a['p_optimal']:.2f}%",
              delta=f"{a['p_optimal'] / a['p_optimal_random']:.0f}x random guess")
    m3.metric("Circuit depth / RZZ gates", f"{cdepth} / {nrzz}")
    m4.metric("Simulation time", f"{secs:.1f}s")
    fig, ax = plt.subplots(figsize=(10, 4))
    shots = sum(counts.values())
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
    labels, vals, cols = [], [], []
    for bs, c in items:
        x = to_x(bs)
        feas = prob.is_feasible(x)
        is_opt = feas and abs(prob.value(x) - opt) < 1e-9
        labels.append((", ".join(f"{v}>{r}" for v, r in prob.assignment(x)) or "(nobody sent)")
                      + ("  [OPTIMAL]" if is_opt else "" if feas else "  [breaks a rule]"))
        vals.append(100 * c / shots)
        cols.append(plots.BLUE if is_opt else ("#86b6ef" if feas else plots.ORANGE))
    y = np.arange(len(items))[::-1]
    ax.barh(y, vals, color=cols)
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlabel("% of 4,096 measurements")
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Exact statevector simulation, no noise. At this size brute force is faster; "
               "the point is a correct quantum formulation, measured honestly.")
