"""
The test instance: a "flood surge" in a small town. Five help requests reach
the ReliefLink server at about the same moment and five volunteers are on duty.

Coordinates are km on the town's street grid (see roads.py). Every request and
volunteer stands at a street corner. The instance is hand-built so that every
spec rule we use shows up at least once:
  - medical cases need first aid, rescues need a swimmer (hard skill filter,
    one of the two options the spec leaves open in §19)
  - a vulnerable household, a late-delivered rescue (aging factor), a
    long-waiting food request
  - a stale volunteer (staleness penalty)
  - a confirmed flood polygon that closes roads and one of the three bridges,
    forcing detours and cutting some volunteers off completely (T5, T6)
  - requests close enough by road that one trip can serve two (our extension)
"""

from dataclasses import dataclass, field
import math
import random

from .roads import build_town


@dataclass
class Request:
    rid: str
    label: str
    req_type: str
    urgency: int
    vulnerable: bool
    people: int
    wait_minutes: float
    x: int
    y: int


@dataclass
class Volunteer:
    vid: str
    label: str
    transport: str
    skills: set = field(default_factory=set)
    trust: float = 0.5
    minutes_since_seen: float = 0.0
    x: int = 0
    y: int = 0


@dataclass
class Scenario:
    requests: list
    volunteers: list
    flood_polygons: list            # list of [(x, y), ...] in km
    town: object = None             # networkx road graph
    max_chain_leg_km: float = 2.0   # our extension: max road km between chained stops
    hard_skill_filter: bool = True  # spec §19 open decision: we choose a hard filter
    max_eta_minutes: float = 45.0   # stand-in for the spec's search radius (§8 Stage 1)
    top_k: int = 2                  # spec §8 Stage 4 notifies the top 3-5; we keep 2 to fit 10 qubits


FLOOD = [[(3.3, 2.5), (5.6, 2.3), (6.2, 3.6), (5.7, 5.3), (3.6, 5.4), (3.1, 4.0)]]


def default_scenario():
    """Requests R1-R4 are requests A-D from the worked priority table in
    Technical Context v2 §7, and R5 is its late-delivery example F (priority
    80.0), so every priority can be checked against the spec by hand."""
    requests = [
        Request("R1", "Medical: injured, vulnerable household (3)", "medical", 5, True, 3, 10, 2, 6),
        Request("R2", "Rescue: family on a roof (6)", "rescue", 5, False, 6, 5, 7, 4),
        Request("R3", "Shelter: 4 people, waiting 45 min", "shelter", 3, False, 4, 45, 3, 7),
        Request("R4", "Food/water: 10 people, waiting 60 min", "food_water", 2, False, 10, 60, 8, 3),
        Request("R5", "Rescue: 2 people, queued 40 min offline", "rescue", 4, False, 2, 40, 6, 2),
    ]
    volunteers = [
        Volunteer("V1", "Bilal: car, first aid + swimmer", "car", {"first_aid", "swimming"}, 0.8, 1, 2, 4),
        Volunteer("V2", "Ayesha: car, first aid", "car", {"first_aid"}, 0.7, 1, 0, 5),
        Volunteer("V3", "Usman: truck, last seen 10 min ago", "truck", set(), 0.5, 10, 9, 6),
        Volunteer("V4", "Sana: bicycle, swimmer", "bicycle", {"swimming"}, 0.9, 1, 8, 1),
        Volunteer("V5", "Ali: car", "car", set(), 0.6, 1, 1, 0),
    ]
    return Scenario(requests, volunteers, FLOOD, build_town())


def random_scenario(n_vol, n_req, seed):
    """Random instance on the same town, for the scaling study only."""
    rnd = random.Random(seed)
    types = ["medical", "rescue", "shelter", "food_water", "transport", "missing"]
    skills = [set(), {"first_aid"}, {"swimming"}, {"first_aid", "swimming"}]
    corners = [(x, y) for x in range(11) for y in range(8)]
    reqs = [Request(f"R{j+1}", "", rnd.choice(types), rnd.randint(1, 5), rnd.random() < 0.3,
                    rnd.randint(1, 10), rnd.uniform(0, 60), *rnd.choice(corners))
            for j in range(n_req)]
    vols = [Volunteer(f"V{i+1}", "", rnd.choice(["car", "truck", "bicycle"]), rnd.choice(skills),
                      round(rnd.uniform(0.3, 0.95), 2), rnd.choice([1, 1, 10]), *rnd.choice(corners))
            for i in range(n_vol)]
    return Scenario(reqs, vols, FLOOD, build_town())


def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)
