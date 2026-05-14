# sim/onit/agent_loader.py
# Loads all 1000 agents from CSV and assigns them to tiers.

import csv
from dataclasses import dataclass, field
from .constants import CSV_PATH, TIER1_CONFIG, TIER2_ROLES


@dataclass
class Agent:
    agent_id:           int
    name:               str
    sex:                str
    age:                int
    role:               str
    family_id:          str
    relation_label:     str
    home_zone:          str
    work_zone:          str
    social_class:       str
    wealth:             float
    income_per_day:     float
    satisfaction:       float
    goals:              list[str]
    is_alive:           bool
    integrity:          float
    greed:              float
    ambition:           float
    family_loyalty:     float
    competence:         float
    empathy:            float
    # assigned at load time
    tier:               int   = 3
    a2a_port:           int   = 0
    agent_key:          str   = ""
    current_location:   str   = ""
    importance_accum:   float = 0.0   # Smallville reflection trigger


def _f(val, default=0.0):
    try:    return float(val)
    except: return default

def _i(val, default=0):
    try:    return int(val)
    except: return default


def load_agents(csv_path: str = CSV_PATH) -> list[Agent]:
    agents: list[Agent] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            agent_id = _i(row.get("agent_id", ""), -1)
            if agent_id < 0:
                continue
            if row.get("is_alive", "True").strip() != "True":
                continue

            goals = [g.strip() for g in row.get("goals", "").split("|") if g.strip()]
            role  = row.get("role", "").strip()

            a = Agent(
                agent_id       = agent_id,
                name           = row.get("name", f"Agent_{agent_id}"),
                sex            = row.get("sex", "M"),
                age            = _i(row.get("age")),
                role           = role,
                family_id      = row.get("family_id", ""),
                relation_label = row.get("relation_label", ""),
                home_zone      = row.get("home_zone", "resA"),
                work_zone      = row.get("work_zone", "resA"),
                social_class   = row.get("social_class", "C"),
                wealth         = _f(row.get("wealth")),
                income_per_day = _f(row.get("income_per_day")),
                satisfaction   = _f(row.get("satisfaction"), 50.0),
                goals          = goals,
                is_alive       = True,
                integrity      = _f(row.get("integrity"),      0.5),
                greed          = _f(row.get("greed"),          0.5),
                ambition       = _f(row.get("ambition"),       0.5),
                family_loyalty = _f(row.get("family_loyalty"), 0.5),
                competence     = _f(row.get("competence"),     0.5),
                empathy        = _f(row.get("empathy"),        0.5),
                current_location = row.get("work_zone", "resA"),
            )

            if agent_id in TIER1_CONFIG:
                cfg          = TIER1_CONFIG[agent_id]
                a.tier       = 1
                a.a2a_port   = cfg["port"]
                a.agent_key  = cfg["key"]
            elif role in TIER2_ROLES:
                a.tier = 2
            else:
                a.tier = 3

            agents.append(a)

    t1 = sum(1 for a in agents if a.tier == 1)
    t2 = sum(1 for a in agents if a.tier == 2)
    t3 = sum(1 for a in agents if a.tier == 3)
    print(f"Loaded {len(agents)} agents: "
          f"{t1} tier-1 (OnIt)  {t2} tier-2 (vLLM)  {t3} tier-3 (rule-based)")
    return agents


def agents_by_tier(agents: list[Agent]) -> tuple[list, list, list]:
    t1 = [a for a in agents if a.tier == 1]
    t2 = [a for a in agents if a.tier == 2]
    t3 = [a for a in agents if a.tier == 3]
    return t1, t2, t3
