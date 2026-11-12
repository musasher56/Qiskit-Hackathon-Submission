"""
ReliefLink formulas, taken directly from "ReliefLink: Technical Context v2".

Every number in this file (weights, speeds, penalties, detour factor) is copied
from the spec. The spec itself labels them as *starting values, not validated
results*, and we carry that caveat into the report.

Sections referenced:
  §7  Priority (triage) rules
  §8  Responder matching: Stage 2 (estimated ETA fallback) and Stage 3 (scoring)
"""

import math

# §7: weight per request type
TYPE_WEIGHT = {
    "rescue": 5, "medical": 5, "transport": 3, "missing": 3,
    "shelter": 2, "food_water": 2, "info": 1,
}

# §8 Stage 3: skill a request type needs (other types need none)
REQUIRED_SKILL = {"medical": "first_aid", "rescue": "swimming"}

# §8 Stage 2 fallback: assumed speeds during flooding, km/h
SPEED_KMH = {"car": 25.0, "bicycle": 10.0, "pedestrian": 4.0, "truck": 20.0}
DETOUR_FACTOR = 1.5

# §8 Stage 3: staleness penalty per location-freshness tier
STALENESS_PENALTY = {"fresh": 0.0, "stale": 0.10, "expired": 0.20}

# §8 Stage 3: scoring weights
W_ETA, W_SKILL, W_EQUIP, W_TRUST, W_WORKLOAD = 0.40, 0.25, 0.15, 0.15, 0.05


def priority(req_type, urgency, vulnerable, people, wait_minutes):
    """§7: type_weight x urgency x vulnerability x crowd x aging."""
    vulnerability = 1.5 if vulnerable else 1.0
    crowd = 1.0 + math.log2(max(people, 1))
    aging = 1.0 + min(wait_minutes / 30.0, 1.0)
    return TYPE_WEIGHT[req_type] * urgency * vulnerability * crowd * aging


def freshness_tier(minutes_since_seen):
    """§8 Stage 1: fresh < 2 min, stale 2-30 min, expired > 30 min."""
    if minutes_since_seen < 2:
        return "fresh"
    if minutes_since_seen <= 30:
        return "stale"
    return "expired"


def estimated_eta_minutes(distance_km, transport):
    """§8 Stage 2 fallback: straight-line x 1.5 / assumed flood speed."""
    return distance_km * DETOUR_FACTOR / SPEED_KMH[transport] * 60.0


def match_score(eta_minutes, skill_ok, equipment_ok, trust, workload, tier):
    """§8 Stage 3:
    0.40*eta_term + 0.25*skill + 0.15*equipment + 0.15*trust
    - 0.05*workload - staleness_penalty,  with eta_term = 1/(1+ETA).
    """
    eta_term = 1.0 / (1.0 + eta_minutes)
    return (W_ETA * eta_term
            + W_SKILL * (1.0 if skill_ok else 0.0)
            + W_EQUIP * (1.0 if equipment_ok else 0.0)
            + W_TRUST * trust
            - W_WORKLOAD * workload
            - STALENESS_PENALTY[tier])
