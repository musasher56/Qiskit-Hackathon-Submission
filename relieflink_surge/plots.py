"""Charts for the report and README (matplotlib, saved as PNG)."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

# Validated categorical palette (fixed order) + neutral ink
BLUE, ORANGE, AQUA, YELLOW, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
VOL_COLORS = [BLUE, ORANGE, AQUA, VIOLET, "#e87ba4"]
# label offsets chosen so labels never sit on an arrow in the default scenario
LABEL_OFFSET = {"R1": (-0.35, -0.1, "right"), "R2": (0.35, 0.05, "left"),
                "R3": (0.3, 0.25, "left"), "R4": (0.35, -0.1, "left")}
REQ_MARK = {"medical": "P", "rescue": "^", "shelter": "s", "food_water": "D", "transport": "h"}

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "figure.facecolor": "white",
    "axes.facecolor": "white", "savefig.dpi": 200, "savefig.bbox": "tight",
})


LAND, ROAD, CASING, MAIN, WATER, FLOOD, FLOOD_EDGE, CLOSED = (
    "#f2efe9", "#ffffff", "#cfc8bc", "#fbe7a1", "#aad3df", "#6fa8dc", "#3d85c6", "#d03b3b")


def draw_map(ax, problem, x=None, title=""):
    """Street-map style drawing: land, river, flood area, roads (closed ones
    in red), then each volunteer's road route for assignment x."""
    from matplotlib.patches import Polygon, Rectangle
    from .roads import RIVER_X, TOWN_W, TOWN_H, MAIN_ROAD_Y
    sc = problem.scenario
    G = sc.town
    ax.set_facecolor(LAND)
    ax.add_patch(Rectangle((RIVER_X - 0.28, -0.6), 0.56, TOWN_H + 1.2, color=WATER, zorder=0))
    for poly in sc.flood_polygons:
        ax.add_patch(Polygon(poly, closed=True, facecolor=FLOOD, alpha=0.35, edgecolor=FLOOD_EDGE,
                             hatch="///", linewidth=1.0, zorder=1))
        cx = sum(p[0] for p in poly) / len(poly)
        ax.text(cx + 0.5, max(p[1] for p in poly) - 0.35, "Flooded", ha="center", fontsize=8,
                color="#0b3d6e", zorder=6, style="italic")
    closed = problem.closed or set()
    for u, v, d in G.edges(data=True):
        xs, ys = [u[0], v[0]], [u[1], v[1]]
        main = d.get("kind") == "main"
        bridge = d.get("kind") == "bridge"
        ax.plot(xs, ys, color="#8f8676" if bridge else CASING, lw=6.5 if (main or bridge) else 5,
                solid_capstyle="round", zorder=2)
        ax.plot(xs, ys, color=MAIN if main else ROAD, lw=4.5 if (main or bridge) else 3.2,
                solid_capstyle="round", zorder=3)
    for u, v in closed:
        ax.plot([u[0], v[0]], [u[1], v[1]], color=CLOSED, lw=1.6, ls=(0, (3, 2)), zorder=4)
        ax.scatter((u[0] + v[0]) / 2, (u[1] + v[1]) / 2, marker="x", s=22, color=CLOSED, lw=1.4, zorder=4)
    ax.text(10.35, MAIN_ROAD_Y, "GT Road", fontsize=7.5, color="#7a6a3a", va="center", ha="left", zorder=6)
    ax.text(RIVER_X, -0.42, "Nullah", fontsize=7.5, color="#2b6a85", ha="center", zorder=6, style="italic")

    if x is not None:
        chosen = {}
        for (i, j), on in zip(problem.variables, x):
            if on:
                chosen.setdefault(i, []).append(j)
        for i, js in chosen.items():
            js = sorted(js, key=lambda j: -problem.priorities[j])
            off = (i - 2) * 0.07
            path = list(problem.routes[(i, js[0])])
            segs = [(path, "-")]
            if len(js) > 1:
                leg = problem.legs[tuple(sorted((js[0], js[1])))]
                leg = leg if leg[0] == path[-1] else leg[::-1]
                segs.append((leg, (0, (2, 1.2))))
            for pts, ls in segs:
                px = [p[0] + off for p in pts]
                py = [p[1] + off for p in pts]
                ax.plot(px, py, color=VOL_COLORS[i], lw=3.2, ls=ls, solid_capstyle="round", zorder=7)
                ax.annotate("", xy=(px[-1], py[-1]), xytext=(px[-2], py[-2]),
                            arrowprops=dict(arrowstyle="-|>", color=VOL_COLORS[i], lw=2, mutation_scale=14),
                            zorder=8)
    for i, v in enumerate(sc.volunteers):
        ax.scatter(v.x, v.y, s=140, color=VOL_COLORS[i], edgecolor="white", linewidth=2, zorder=9)
        ax.text(v.x, v.y - 0.42, v.vid, ha="center", fontsize=8.5, color=INK, zorder=10,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))
    for j, r in enumerate(sc.requests):
        ax.scatter(r.x, r.y, s=150, marker=REQ_MARK.get(r.req_type, "o"), color="white",
                   edgecolor=INK, linewidth=1.5, zorder=9)
        ax.text(r.x + 0.22, r.y + 0.22, f"{r.rid} ({problem.priorities[j]:.0f})", fontsize=8.5,
                color=INK, zorder=10, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    ax.set_xlim(-0.6, TOWN_W + 1.1)
    ax.set_ylim(-0.7, TOWN_H + 0.6)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s_ in ax.spines.values():
        s_.set_visible(True); s_.set_color(GRID)
    ax.set_title(title, fontsize=10, color=INK, loc="left")


def legend_handles(problem):
    from matplotlib.lines import Line2D
    sc = problem.scenario
    h = [Line2D([], [], marker="o", ls="", color=VOL_COLORS[i], markersize=8,
                label=v.label) for i, v in enumerate(sc.volunteers)]
    h += [Line2D([], [], marker=REQ_MARK.get(r.req_type, "o"), ls="", markerfacecolor="white",
                 markeredgecolor=INK, markersize=8, label=f"{r.rid}: {r.label}")
          for r in sc.requests]
    h += [Line2D([], [], color=CLOSED, ls=(0, (3, 2)), marker="x", label="Road closed by flood"),
          Line2D([], [], color="#555555", lw=2.5, ls=(0, (2, 1.2)), label="Second stop on a chained trip")]
    return h


def map_panels(problem, panels, path):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2))
    for ax, (title, x) in zip(axes.flat, panels):
        draw_map(ax, problem, x, title)
    fig.legend(handles=legend_handles(problem), loc="lower center", ncol=3, frameon=False,
               fontsize=8, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def scenario_only(problem, path):
    fig, ax = plt.subplots(figsize=(8, 5.4))
    sc = problem.scenario
    draw_map(ax, problem, None, f"Flood surge: {len(sc.requests)} requests, {len(sc.volunteers)} volunteers (priority in brackets)")
    ax.legend(handles=legend_handles(problem), loc="upper left", bbox_to_anchor=(1.01, 1),
              frameon=False, fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def method_bars(rows, optimum, path):
    """rows: list of (name, value, is_quantum)."""
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    cols = [BLUE if r[2] else "#9a9993" for r in rows]
    y = np.arange(len(rows))[::-1]
    ax.barh(y, vals, color=cols, height=0.62)
    for yi, v in zip(y, vals):
        ax.text(v + 1.5, yi, f"{v:.1f}  ({100 * v / optimum:.0f}%)", va="center",
                fontsize=9, color=INK)
    ax.set_yticks(y, names)
    ax.set_xlim(0, optimum * 1.3)
    ax.set_xlabel("Relief value (higher is better; % of exact optimum)")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#9a9993", label="Classical"), Patch(color=BLUE, label="Quantum (QAOA)")],
              frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2, fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)


def distribution(problem, counts, to_x, optimum, path, top=12):
    shots = sum(counts.values())
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:top]
    labels, probs, colors = [], [], []
    for bs, c in items:
        x = to_x(bs)
        a = problem.assignment(x)
        lab = ", ".join(f"{v}>{r}" for v, r in a) or "(nobody sent)"
        feas = problem.is_feasible(x)
        is_opt = feas and abs(problem.value(x) - optimum) < 1e-9
        labels.append(lab + ("  [OPTIMAL]" if is_opt else "" if feas else "  [breaks a rule]"))
        probs.append(c / shots)
        colors.append(BLUE if is_opt else ("#86b6ef" if feas else ORANGE))
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    y = np.arange(len(items))[::-1]
    ax.barh(y, probs, color=colors, height=0.65)
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlabel("Share of 4,096 measurements")
    from matplotlib.ticker import PercentFormatter
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="Optimal"), Patch(color="#86b6ef", label="Valid, not optimal"),
                       Patch(color=ORANGE, label="Breaks a rule")],
              frameon=False, fontsize=8.5, loc="lower right")
    fig.savefig(path)
    plt.close(fig)


def depth_sweep(sweep, p_random, path):
    """sweep: {objective: [(p, p_opt, p_feas, mf_ratio), ...]}"""
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    styles = {"standard": (BLUE, "o", "Standard QAOA"), "cvar": (ORANGE, "s", "CVaR-QAOA")}
    for obj, rows in sweep.items():
        c, m, lab = styles[obj]
        ps = [r[0] for r in rows]
        # a run that never measured the optimum (0 of 4,096 shots) can't sit on a log axis: leave a gap
        axes[0].plot(ps, [100 * r[1] if r[1] > 0 else np.nan for r in rows], color=c, marker=m, lw=2, ms=8, label=lab)
        axes[1].plot(ps, [100 * r[3] for r in rows], color=c, marker=m, lw=2, ms=8, label=lab)
    axes[0].axhline(100 * p_random, color=INK2, ls="--", lw=1)
    axes[0].text(1, 100 * p_random * 1.3, "random guess", fontsize=8, color=INK2)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("P(exact optimum) %, log scale")
    axes[1].set_ylabel("Most frequent valid answer\n(% of optimum)")
    for ax in axes:
        ax.set_xlabel("QAOA depth p")
        ax.set_xticks(sorted({r[0] for rows in sweep.values() for r in rows}))
        ax.grid(color=GRID, lw=0.6)
        ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def penalty_sweep(rows, path):
    """rows: [(factor, p_feas, p_opt)] - two panels, one measure each (no dual axis)."""
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
    f = [r[0] for r in rows]
    from matplotlib.ticker import NullFormatter
    for ax, k, col, mk, lab in [(axes[0], 1, BLUE, "o", "P(valid answer) %"),
                                (axes[1], 2, ORANGE, "s", "P(exact optimum) %")]:
        ax.plot(f, [100 * r[k] for r in rows], color=col, marker=mk, lw=2, ms=8)
        ax.set_xscale("log")
        ax.set_xticks(f, [f"{v}x" for v in f])
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Penalty P (multiple of largest reward)")
        ax.set_ylabel(lab)
        ax.set_ylim(bottom=0)
        ax.grid(color=GRID, lw=0.6)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def scaling(rows, path):
    """rows: [(qubits, p_opt_qaoa, p_opt_random)]"""
    fig, ax = plt.subplots(figsize=(6, 3.2))
    q = [r[0] for r in rows]
    ax.scatter(q, [100 * r[1] for r in rows], color=BLUE, s=60, label="CVaR-QAOA (p=3)", zorder=3)
    qs = np.arange(min(q), max(q) + 1)
    ax.plot(qs, 100 / 2.0 ** qs, color=INK2, ls="--", lw=1, label="Random guess (1/2^n)")
    ax.set_yscale("log")
    ax.set_xlabel("Qubits (usable volunteer-request pairs)")
    ax.set_ylabel("P(exact optimum) %")
    ax.grid(color=GRID, lw=0.6)
    ax.legend(frameon=False, fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)
