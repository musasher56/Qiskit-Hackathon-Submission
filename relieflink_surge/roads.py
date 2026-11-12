"""
A synthetic road network for a flood-hit town, so travel times follow roads
instead of straight lines (spec §8 Stage 2, "Normal" mode: road-based ETA with
hazard zones avoided).

The town is a 1 km street grid split by a river (a nullah). Only three
bridges cross it. A confirmed flood polygon closes every road segment it
touches, including one bridge, so some volunteers must detour and some cannot
reach some requests at all (spec tests T5 and T6).

The road network is invented, not real map data. We say so in the report: real
OpenStreetMap roads would drop in here without changing anything else.
"""

import networkx as nx

TOWN_W, TOWN_H = 10, 7          # km
RIVER_X = 4.5                   # river runs north-south between x=4 and x=5
BRIDGES_Y = (1, 4, 6)           # only these east-west segments cross it
MAIN_ROAD_Y = 4                 # "GT Road", drawn wider


def build_town():
    G = nx.Graph()
    for x in range(TOWN_W + 1):
        for y in range(TOWN_H + 1):
            G.add_node((x, y))
    for x in range(TOWN_W + 1):
        for y in range(TOWN_H + 1):
            if x < TOWN_W:
                crosses_river = x < RIVER_X < x + 1
                if not crosses_river or y in BRIDGES_Y:
                    kind = "bridge" if crosses_river else ("main" if y == MAIN_ROAD_Y else "street")
                    G.add_edge((x, y), (x + 1, y), length=1.0, kind=kind)
            if y < TOWN_H:
                G.add_edge((x, y), (x, y + 1), length=1.0, kind="street")
    return G


# ---------- polygon geometry (no external GIS dependency) ----------

def point_in_polygon(px, py, poly):
    inside = False
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        if (y1 > py) != (y2 > py):
            xc = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xc:
                inside = not inside
    return inside


def _segments_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def segment_hits_polygon(a, b, poly):
    if point_in_polygon(*a, poly) or point_in_polygon(*b, poly):
        return True
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if point_in_polygon(*mid, poly):
        return True
    n = len(poly)
    return any(_segments_cross(a, b, poly[k], poly[(k + 1) % n]) for k in range(n))


def closed_edges(G, flood_polygons):
    """Every road segment touching a confirmed flood polygon is closed."""
    return {tuple(sorted((u, v))) for u, v in G.edges
            if any(segment_hits_polygon(u, v, poly) for poly in flood_polygons)}


def open_network(G, flood_polygons):
    H = G.copy()
    H.remove_edges_from(closed_edges(G, flood_polygons))
    return H


def road_route(H, a, b):
    """(path, km) along open roads, or (None, None) if cut off."""
    try:
        path = nx.shortest_path(H, a, b, weight="length")
        km = nx.path_weight(H, path, weight="length")
        return path, km
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, None
