"""
barangay_mechanics.py

Barangay-specific simulation mechanics layered on top of generative_agents.
Provides:
  1. Dynasty trust initialization — agents in the same family start with
     positive relationship memories toward each other.
  2. Corruption metric tracking — estimates a per-step corruption score from
     agent traits + political positions and logs it to a CSV.

Usage (called from reverie.py):
  from barangay_mechanics import inject_dynasty_memories, log_corruption_step
"""
import csv
import os
import datetime

# ---------------------------------------------------------------------------
# 1. Dynasty Trust Initialization
# ---------------------------------------------------------------------------

# Political roles whose family membership matters for dynasty detection
POLITICAL_ROLES = {
    "mayor", "vice_mayor", "councilor", "barangay_captain", "contractor"
}

def load_agent_family_map(csv_path):
    """
    Returns dict: {agent_name: family_id} for agents with a non-null family_id.
    Also returns dict: {family_id: [agent_names]} for group lookups.
    """
    name_to_family = {}
    family_to_names = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name"].strip()
            fid  = row.get("family_id", "").strip()
            if fid:
                name_to_family[name] = fid
                family_to_names.setdefault(fid, []).append(name)
    return name_to_family, family_to_names


def inject_dynasty_memories(personas, csv_path):
    """
    For each agent in a political dynasty (same family_id), inject an initial
    memory into every family member's associative memory that describes their
    relationship. This seeds the LLM's relationship retrieval with dynasty bonds.

    personas: dict {name: Persona} from ReverieServer
    csv_path: path to barangay_agents.csv
    """
    if not os.path.exists(csv_path):
        print(f"[barangay] CSV not found at {csv_path}, skipping dynasty init.")
        return

    name_to_family, family_to_names = load_agent_family_map(csv_path)
    injected = 0

    for persona_name, persona in personas.items():
        fid = name_to_family.get(persona_name)
        if not fid:
            continue

        family_members = [n for n in family_to_names[fid] if n != persona_name
                          and n in personas]
        if not family_members:
            continue

        for member_name in family_members:
            desc = (f"{persona_name} and {member_name} are members of the "
                    f"{fid} political family. They share a strong bond of "
                    f"trust and loyalty.")
            try:
                persona.a_mem.add_thought(
                    created    = persona.scratch.curr_time or datetime.datetime(2024, 2, 13, 7, 0, 0),
                    expiration = None,
                    s          = persona_name,
                    p          = "is family with",
                    o          = member_name,
                    keywords   = {persona_name, member_name, fid, "family", "trust"},
                    thought_poignancy  = 8,
                    thought_embedding_pair = (desc, [0.0] * 384),
                    evidence   = []
                )
                injected += 1
            except Exception as e:
                # a_mem API may vary; log and continue
                print(f"[barangay] Could not inject dynasty memory for "
                      f"{persona_name}↔{member_name}: {e}")

    print(f"[barangay] Dynasty memories injected: {injected} relationships.")


# ---------------------------------------------------------------------------
# 2. Corruption Metric Tracking
# ---------------------------------------------------------------------------

# Weight of each role's corruption contribution
ROLE_WEIGHTS = {
    "mayor":           1.5,
    "vice_mayor":      1.2,
    "councilor":       1.0,
    "barangay_captain":1.0,
    "contractor":      0.8,
    "auditor":        -1.0,   # auditors reduce corruption
    "journalist":     -0.5,   # journalists suppress corruption
    "police":         -0.3,
}


def _estimate_agent_corruption(persona, agent_row):
    """
    Heuristic corruption score for a single agent based on their traits.
    Returns a float in [0, 1].
    """
    greed     = float(agent_row.get("greed",     0.5))
    integrity = float(agent_row.get("integrity", 0.5))
    ambition  = float(agent_row.get("ambition",  0.5))
    # Corruption increases with greed & ambition, decreases with integrity
    raw = (greed * 0.5) + (ambition * 0.2) + ((1 - integrity) * 0.3)
    return max(0.0, min(1.0, raw))


def log_corruption_step(personas, agent_rows_by_name, step, curr_time, output_path,
                        event_bonus=0.0):
    """
    Compute a barangay-wide corruption index for this sim step and append it
    to a running CSV log at <output_path>/corruption_log.csv.

    personas:          dict {name: Persona}
    agent_rows_by_name: dict {name: csv_row_dict} loaded once at sim start
    step:              current simulation step integer
    curr_time:         datetime of current step
    output_path:       directory path for output files
    event_bonus:       persistent corruption accumulated from active corruption
                       events (barangay_corruption_events). Trait-based index is
                       a baseline; events add on top so the 10-step recompute does
                       not erase witnessed corruption.

    Returns dict: {corruption_index, welfare_score, unrest, dynasty_bonus}.
    """
    os.makedirs(output_path, exist_ok=True)
    log_file = os.path.join(output_path, "corruption_log.csv")

    total_weight = 0.0
    weighted_corruption = 0.0
    dynasty_bonus = 0.0

    family_in_office = {}   # family_id → count of political agents
    for name, persona in personas.items():
        row = agent_rows_by_name.get(name)
        if not row:
            continue
        role   = row.get("role", "")
        weight = ROLE_WEIGHTS.get(role, 0.0)
        fid    = row.get("family_id", "").strip()

        if weight != 0:
            agent_corr = _estimate_agent_corruption(persona, row)
            weighted_corruption += weight * agent_corr
            total_weight += abs(weight)

        if role in POLITICAL_ROLES and fid:
            family_in_office[fid] = family_in_office.get(fid, 0) + 1

    # Dynasty bonus: each family with 2+ members in office adds corruption
    for fid, count in family_in_office.items():
        if count >= 2:
            dynasty_bonus += (count - 1) * 0.05

    corruption_index = (weighted_corruption / total_weight if total_weight else 0.0)
    corruption_index = max(0.0, min(1.0, corruption_index + dynasty_bonus + event_bonus))

    # Derived welfare & unrest (the feedback loop the news bulletin surfaces):
    # welfare starts from the population's mean satisfaction and is dragged down
    # by corruption; unrest rises with corruption and falls with welfare.
    sats = [float(r.get("satisfaction", 50)) for r in agent_rows_by_name.values()
            if r.get("satisfaction") not in (None, "")]
    base_welfare = (sum(sats) / len(sats) / 100.0) if sats else 0.5
    welfare_score = max(0.0, min(1.0, base_welfare * (1.0 - 0.5 * corruption_index)))
    unrest = max(0.0, min(1.0, 0.15 + 0.6 * corruption_index - 0.4 * (welfare_score - 0.5)))

    write_header = not os.path.exists(log_file)
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["step", "datetime", "corruption_index", "dynasty_bonus",
                             "welfare", "unrest"])
        writer.writerow([
            step,
            curr_time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{corruption_index:.4f}",
            f"{dynasty_bonus:.4f}",
            f"{welfare_score:.4f}",
            f"{unrest:.4f}",
        ])

    return {"corruption_index": corruption_index, "welfare_score": welfare_score,
            "unrest": unrest, "dynasty_bonus": dynasty_bonus}


def load_agent_rows(csv_path):
    """
    Load barangay_agents.csv into a dict keyed by agent name.
    Call once at sim startup.
    """
    rows = {}
    if not os.path.exists(csv_path):
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["name"].strip()] = row
    return rows
