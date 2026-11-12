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


EXTENT = (-0.6, 11.1, -0.7, 7.6)       # map window in km: x0, x1, y0, y1
_SAT_CACHE = {}


def _satellite_raster(px_per_km=48, seed=3):
    """Procedural satellite-style ground texture (illustrative only, not real
    imagery): rooftops in town blocks, a few green plots, farmland outside
    town, and a muddy river. Seeded, so it looks the same every run."""
    key = (px_per_km, seed)
    if key in _SAT_CACHE:
        return _SAT_CACHE[key]
    from .roads import RIVER_X, TOWN_W, TOWN_H
    rng = np.random.default_rng(seed)
    x0, x1, y0, y1 = EXTENT
    W, H = int((x1 - x0) * px_per_km), int((y1 - y0) * px_per_km)
    xs = x0 + (np.arange(W) + 0.5) / px_per_km
    ys = y0 + (np.arange(H) + 0.5) / px_per_km
    X, Y = np.meshgrid(xs, ys)

    def smooth_noise(cells):
        g = rng.random((cells + 2, cells + 2))
        gx = (X - x0) / (x1 - x0) * cells
        gy = (Y - y0) / (y1 - y0) * cells
        ix, iy = gx.astype(int), gy.astype(int)
        fx, fy = gx - ix, gy - iy
        return ((g[iy, ix] * (1 - fx) + g[iy, ix + 1] * fx) * (1 - fy)
                + (g[iy + 1, ix] * (1 - fx) + g[iy + 1, ix + 1] * fx) * fy)

    n1, n2 = smooth_noise(14), smooth_noise(40)
    grain = rng.normal(0, 1, X.shape)
    # farmland: greens and dry browns in patches
    field_a, field_b = np.array([0.36, 0.42, 0.24]), np.array([0.55, 0.50, 0.36])
    t = np.clip(n1 * 1.3 - 0.15, 0, 1)[..., None]
    img = field_a * (1 - t) + field_b * t
    img += (n2[..., None] - 0.5) * 0.08 + grain[..., None] * 0.012
    # town blocks: rooftops separated by alleys
    in_town = (X > 0.06) & (X < TOWN_W - 0.06) & (Y > 0.06) & (Y < TOWN_H - 0.06)
    u, v = np.mod(X, 1.0), np.mod(Y, 1.0)
    bx, by = np.floor(X).astype(int), np.floor(Y).astype(int)
    hx, hy = np.floor(u * 5).astype(int), np.floor(v * 5).astype(int)
    alley = (np.mod(u * 5, 1) < 0.14) | (np.mod(v * 5, 1) < 0.14)
    roofs = np.array([[0.72, 0.66, 0.58], [0.63, 0.60, 0.57], [0.66, 0.47, 0.38], [0.80, 0.77, 0.70],
                      [0.52, 0.50, 0.48], [0.70, 0.60, 0.48], [0.58, 0.54, 0.50]])
    hid = (bx * 7919 + by * 104729 + hx * 31 + hy * 17) % 1000003
    roof = roofs[(hid * 2654435761 % 2 ** 32) % len(roofs)]
    roof = roof * (0.78 + 0.22 * ((hid % 97) / 97.0))[..., None]
    roof = roof * (0.92 + 0.16 * n2[..., None])
    park_block = ((bx * 13 + by * 7) % 9 == 0)
    town_col = np.where(alley[..., None], np.array([0.40, 0.38, 0.35]), roof)
    town_col = np.where(park_block[..., None], np.array([0.30, 0.42, 0.24]) + (n2[..., None] - 0.5) * 0.1, town_col)
    town_col = town_col + grain[..., None] * 0.03
    img = np.where(in_town[..., None], town_col, img)
    # river: muddy green-brown water
    river = np.abs(X - RIVER_X) < 0.28 + 0.03 * np.sin(Y * 3)
    water = np.array([0.33, 0.40, 0.38]) + (n2[..., None] - 0.5) * 0.06
    img = np.where(river[..., None], water, img)
    img = np.clip(img, 0, 1)
    _SAT_CACHE[key] = img
    return img


def _flood_raster(seed=5):
    rng = np.random.default_rng(seed)
    x0, x1, y0, y1 = EXTENT
    W, H = int((x1 - x0) * 48), int((y1 - y0) * 48)
    base = np.array([0.47, 0.40, 0.29])
    n = rng.normal(0, 1, (H // 6 + 1, W // 6 + 1))
    n = np.kron(n, np.ones((6, 6)))[:H, :W]
    return np.clip(base + n[..., None] * 0.025, 0, 1)


def _halo(lw=3):
    import matplotlib.patheffects as pe
    return [pe.withStroke(linewidth=lw, foreground="black")]


def draw_map(ax, problem, x=None, title="", style="street"):
    """Map drawing in "street" or "satellite" style: ground, river, flood
    area, roads (closed ones in red), then each volunteer's road route."""
    from matplotlib.patches import Polygon, Rectangle
    from .roads import RIVER_X, TOWN_W, TOWN_H, MAIN_ROAD_Y
    sc = problem.scenario
    G = sc.town
    sat = style == "satellite"
    if sat:
        ax.imshow(_satellite_raster(), extent=EXTENT, origin="lower", zorder=0, interpolation="bilinear")
        for poly in sc.flood_polygons:
            patch = Polygon(poly, closed=True, facecolor="none", edgecolor="#e8d9a8", lw=1.0, ls="--", zorder=5)
            im = ax.imshow(_flood_raster(), extent=EXTENT, origin="lower", zorder=4, alpha=0.88)
            ax.add_patch(patch)
            im.set_clip_path(patch)
            cx = sum(p[0] for p in poly) / len(poly)
            ax.text(cx + 0.5, max(p[1] for p in poly) - 0.35, "Floodwater", ha="center", fontsize=8,
                    color="white", zorder=6, style="italic", path_effects=_halo(2.5))
    else:
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
        if sat:
            ax.plot(xs, ys, color="#3d3b38", lw=4.2 if (main or bridge) else 3.2, solid_capstyle="butt", zorder=2)
            ax.plot(xs, ys, color="#8a857b" if main else "#6f6b64", lw=3.0 if (main or bridge) else 2.0,
                    solid_capstyle="butt", zorder=3)
        else:
            ax.plot(xs, ys, color="#8f8676" if bridge else CASING, lw=6.5 if (main or bridge) else 5,
                    solid_capstyle="round", zorder=2)
            ax.plot(xs, ys, color=MAIN if main else ROAD, lw=4.5 if (main or bridge) else 3.2,
                    solid_capstyle="round", zorder=3)
    for u, v in closed:
        ax.plot([u[0], v[0]], [u[1], v[1]], color="#ff4d4d" if sat else CLOSED, lw=1.6, ls=(0, (3, 2)), zorder=6)
        ax.scatter((u[0] + v[0]) / 2, (u[1] + v[1]) / 2, marker="x", s=22,
                   color="#ff4d4d" if sat else CLOSED, lw=1.4, zorder=6)
    lab_kw = dict(color="white", path_effects=_halo(2.5)) if sat else {}
    ax.text(10.35, MAIN_ROAD_Y, "GT Road", fontsize=7.5, va="center", ha="left", zorder=6,
            **(lab_kw or {"color": "#7a6a3a"}))
    ax.text(RIVER_X, -0.42, "Nullah", fontsize=7.5, ha="center", zorder=6, style="italic",
            **(lab_kw or {"color": "#2b6a85"}))

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
                ax.plot(px, py, color=VOL_COLORS[i], lw=3.2, ls=ls, solid_capstyle="round", zorder=7,
                        path_effects=_halo(5.5) if sat else None)
                ax.annotate("", xy=(px[-1], py[-1]), xytext=(px[-2], py[-2]),
                            arrowprops=dict(arrowstyle="-|>", color=VOL_COLORS[i], lw=2, mutation_scale=14),
                            zorder=8)
    for i, v in enumerate(sc.volunteers):
        ax.scatter(v.x, v.y, s=140, color=VOL_COLORS[i], edgecolor="white", linewidth=2, zorder=9)
        ax.text(v.x, v.y - 0.42, v.vid, ha="center", fontsize=8.5, color=INK, zorder=10,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
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


def map_panels(problem, panels, path, style="street"):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2))
    for ax, (title, x) in zip(axes.flat, panels):
        draw_map(ax, problem, x, title, style=style)
    fig.legend(handles=legend_handles(problem), loc="lower center", ncol=3, frameon=False,
               fontsize=8, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def scenario_only(problem, path, style="street"):
    fig, ax = plt.subplots(figsize=(8, 5.4))
    sc = problem.scenario
    draw_map(ax, problem, None, f"Flood surge: {len(sc.requests)} requests, {len(sc.volunteers)} volunteers (priority in brackets)",
             style=style)
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
