# sim/onit/location_engine.py
# Tracks agent locations, handles movement, returns co-present pairs.
# Agents move between home_zone and work_zone based on tick parity,
# with a small chance of visiting community locations.

import random
import sqlite3
from datetime import datetime, timezone
from .constants import DB_PATH, INTERACT_CHANCE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .agent_loader import Agent

COMMUNITY_ZONES = {"market", "church", "plaza", "park"}

_DAYTIME_TICKS = set(range(0, 24, 2))   # even ticks = daytime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_location_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_locations (
            agent_id   INTEGER PRIMARY KEY,
            agent_name TEXT    NOT NULL,
            location   TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def update_locations(agents: list["Agent"], tick: int) -> None:
    """Move all agents to their appropriate location for this tick."""
    is_daytime = (tick % 24) in _DAYTIME_TICKS

    conn = sqlite3.connect(DB_PATH)
    for a in agents:
        if is_daytime:
            loc = a.work_zone
        else:
            loc = a.home_zone

        # Small chance of visiting a community spot instead
        if a.tier <= 2 and random.random() < 0.08:
            loc = random.choice(list(COMMUNITY_ZONES))

        a.current_location = loc
        conn.execute(
            "INSERT OR REPLACE INTO agent_locations "
            "(agent_id, agent_name, location, updated_at) VALUES (?,?,?,?)",
            (a.agent_id, a.name, loc, _now()),
        )
    conn.commit()
    conn.close()


def get_location_map(agents: list["Agent"]) -> dict[str, list["Agent"]]:
    """Return {location: [agents_there]} for the current tick."""
    loc_map: dict[str, list] = {}
    for a in agents:
        loc_map.setdefault(a.current_location, []).append(a)
    return loc_map


def find_interaction_pairs(agents: list["Agent"]) -> list[tuple["Agent", "Agent", str]]:
    """
    Return list of (agent_a, agent_b, location) pairs eligible for interaction.
    Only pairs where at least one agent is tier 1 or 2.
    """
    loc_map  = get_location_map(agents)
    eligible = []

    for location, present in loc_map.items():
        # Only care if there are 2+ political agents
        political = [a for a in present if a.tier <= 2]
        if len(political) < 2:
            continue

        # Sample pairs without replacement
        sampled = random.sample(political, min(len(political), 4))
        seen    = set()
        for i, a in enumerate(sampled):
            for b in sampled[i+1:]:
                pair_key = tuple(sorted([a.agent_id, b.agent_id]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                if random.random() < INTERACT_CHANCE:
                    eligible.append((a, b, location))

    return eligible
