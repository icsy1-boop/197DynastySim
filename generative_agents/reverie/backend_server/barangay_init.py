"""
barangay_init.py

Converts barangay_agents.csv into generative_agents persona bootstrap files.
Run from reverie/backend_server/:

  python barangay_init.py [--roles all|key] [--csv PATH] [--sim NAME]

--roles key  (default) initializes only political & enforcement agents (~30-50)
--roles all  initializes all 2,716 agents (slow; run after Qwen is verified)
"""
import csv
import json
import os
import argparse

# ---------------------------------------------------------------------------
# Paths (relative to reverie/backend_server/)
# ---------------------------------------------------------------------------
STORAGE_ROOT = "../../environment/frontend_server/storage"
DEFAULT_CSV   = "../../../barangay_agents.csv"  # root of 197 repo
WORLD_NAME    = "Barangay Mabuhay"

# ---------------------------------------------------------------------------
# Zone mappings: CSV zone code → (sector, arena, [objects])
# ---------------------------------------------------------------------------
ZONE_MAP = {
    # Home zones
    "resA": (f"{WORLD_NAME}:Residential Zone A:home",
             ["bed", "closet", "desk", "refrigerator"]),
    "resB": (f"{WORLD_NAME}:Residential Zone B:home",
             ["bed", "closet", "desk", "refrigerator"]),
    "resC": (f"{WORLD_NAME}:Residential Zone C:home",
             ["bed", "closet", "desk", "refrigerator"]),

    # Work zones
    "munhall":    (f"{WORLD_NAME}:Municipal Hall:office",
                   ["mayor's desk", "meeting table", "file cabinet", "reception desk"]),
    "bgyhall":    (f"{WORLD_NAME}:Barangay Hall:office",
                   ["captain's desk", "council table", "bulletin board", "reception desk"]),
    "audit":      (f"{WORLD_NAME}:Audit Office:office",
                   ["auditor's desk", "file cabinet", "computer"]),
    "contoffice": (f"{WORLD_NAME}:Contractor Office:office",
                   ["contractor's desk", "blueprint table", "file cabinet"]),
    "police":     (f"{WORLD_NAME}:Police Station:station",
                   ["officer's desk", "holding area", "dispatch radio"]),
    "hospital":   (f"{WORLD_NAME}:Health Center:clinic",
                   ["nurse's station", "examination bed", "medicine cabinet", "waiting area"]),
    "school":     (f"{WORLD_NAME}:School:classroom",
                   ["teacher's desk", "student desks", "blackboard", "library shelf"]),
    "church":     (f"{WORLD_NAME}:Church:chapel",
                   ["altar", "pews", "prayer candles"]),
    "farm":       (f"{WORLD_NAME}:Farm Area:field",
                   ["crop field", "irrigation pump", "storage shed", "harvest area"]),
    "market":     (f"{WORLD_NAME}:Public Market:stall",
                   ["vendor stall", "market counter", "storage crates"]),
    "media":      (f"{WORLD_NAME}:Media Office:newsroom",
                   ["journalist's desk", "camera equipment", "printer"]),
    "park":       (f"{WORLD_NAME}:Plaza:park",
                   ["park bench", "fountain", "basketball court"]),
}

# ---------------------------------------------------------------------------
# Roles that count as "key" (political + enforcement) for --roles key
# ---------------------------------------------------------------------------
KEY_ROLES = {
    "mayor", "vice_mayor", "councilor", "barangay_captain",
    "auditor", "police", "journalist", "contractor",
}

# ---------------------------------------------------------------------------
# Role → daily schedule summary
# ---------------------------------------------------------------------------
ROLE_SCHEDULE = {
    "mayor":           "goes to Municipal Hall by 8am, holds meetings and signs documents until 5pm, attends evening community events occasionally.",
    "vice_mayor":      "arrives at Municipal Hall by 8am, assists the mayor and chairs council sessions until 5pm.",
    "councilor":       "attends Barangay Hall sessions at 9am, conducts community consultations, and returns home by 6pm.",
    "barangay_captain":"opens Barangay Hall at 7am, mediates disputes, oversees programs, and closes by 7pm.",
    "auditor":         "arrives at the Audit Office by 8am, reviews financial records and conducts inspections until 5pm.",
    "police":          "reports to the Police Station at 6am, patrols the barangay, and ends shift at 6pm.",
    "journalist":      "works at the Media Office mornings, covers events around the barangay afternoons.",
    "contractor":      "visits the Contractor Office at 8am, inspects project sites throughout the day.",
    "nurse":           "reports to the Health Center at 7am, attends to patients until 4pm.",
    "teacher":         "arrives at School by 7am, teaches classes until 3pm.",
    "farmer":          "wakes at 5am, works in the farm field all morning, returns home by noon.",
    "vendor":          "sets up at the Public Market by 6am, sells goods until early evening.",
    "business_owner":  "opens shop at the Public Market by 8am and manages business until 7pm.",
    "student":         "attends school from 7am to 3pm, studies at home in the evenings.",
    "elder":           "wakes early, visits the church in the morning, rests in the afternoon.",
    "unemployed":      "wakes late, spends time at the plaza or market looking for opportunities.",
    "informal_worker": "takes whatever odd jobs are available around the barangay each day.",
}

# ---------------------------------------------------------------------------
# Trait → adjective mapping for building personality description
# ---------------------------------------------------------------------------
def trait_adjectives(row):
    """Convert numeric trait scores into descriptive adjectives for innate field."""
    parts = []

    def level(val, low="low", mid="moderate", high="high"):
        v = float(val)
        if v >= 0.7: return high
        if v >= 0.4: return mid
        return low

    integrity = float(row["integrity"])
    greed     = float(row["greed"])
    ambition  = float(row["ambition"])
    empathy   = float(row["empathy"])
    competence= float(row["competence"])
    family_loyalty = float(row["family_loyalty"])

    if integrity >= 0.7:   parts.append("honest")
    elif integrity < 0.35: parts.append("dishonest")

    if greed >= 0.7:       parts.append("greedy")
    elif greed < 0.35:     parts.append("selfless")

    if ambition >= 0.7:    parts.append("ambitious")
    elif ambition < 0.35:  parts.append("content")

    if empathy >= 0.7:     parts.append("empathetic")
    elif empathy < 0.35:   parts.append("callous")

    if competence >= 0.7:  parts.append("highly competent")
    elif competence < 0.35:parts.append("inexperienced")

    if family_loyalty >= 0.7: parts.append("deeply loyal to family")

    return ", ".join(parts) if parts else "ordinary"


def make_scratch(row):
    name = row["name"].strip()
    parts = name.split()
    first = parts[0]
    last  = " ".join(parts[1:]) if len(parts) > 1 else ""

    role       = row["role"].replace("_", " ")
    social     = row["social_class"]
    age        = int(row["age"])
    edu        = int(row["education_level"])
    goals_raw  = row.get("goals", "").strip()
    goals_list = [g.strip() for g in goals_raw.split("|") if g.strip()]
    goals_str  = "; ".join(goals_list[:3]) if goals_list else "live a decent life"
    family_id  = row.get("family_id", "").strip() or None
    home_zone  = row.get("home_zone", "resA")
    work_zone  = row.get("work_zone", "park")
    satisfaction = float(row.get("satisfaction", 50))

    innate  = trait_adjectives(row)
    edu_desc = ["uneducated", "elementary graduate", "high school student",
                "high school graduate", "college graduate", "post-graduate"][min(edu, 5)]

    learned = (
        f"{name} is a {role} in {WORLD_NAME}, {social} class, {age} years old, "
        f"{edu_desc}. "
    )
    if family_id:
        learned += f"They belong to the {family_id} political family. "
    learned += (
        f"They earn {float(row['income_per_day']):.0f} pesos per day and have "
        f"accumulated {float(row['wealth']):.0f} pesos in wealth. "
        f"Their satisfaction with life is currently {satisfaction:.0f}/100."
    )

    currently = f"{name} is focused on: {goals_str}."

    schedule_text = ROLE_SCHEDULE.get(row["role"],
        "follows a typical daily routine based on their role and responsibilities.")
    lifestyle = f"{name} wakes up around 6am, {schedule_text} Goes to bed around 10pm."

    home_address, _ = ZONE_MAP.get(home_zone, ZONE_MAP["resA"])

    daily_plan = (
        f"{name} works as a {role} in {WORLD_NAME}. "
        + ROLE_SCHEDULE.get(row["role"], "Follows a standard daily routine.")
    )

    return {
        "vision_r": 8,
        "att_bandwidth": 8,
        "retention": 8,
        "curr_time": None,
        "curr_tile": None,
        "daily_plan_req": daily_plan,
        "name": name,
        "first_name": first,
        "last_name": last,
        "age": age,
        "innate": innate,
        "learned": learned,
        "currently": currently,
        "lifestyle": lifestyle,
        "living_area": home_address,
        "concept_forget": 100,
        "daily_reflection_time": 180,
        "daily_reflection_size": 5,
        "overlap_reflect_th": 4,
        "kw_strg_event_reflect_th": 10,
        "kw_strg_thought_reflect_th": 9,
        "recency_w": 1,
        "relevance_w": 1,
        "importance_w": 1,
        "recency_decay": 0.995,
        "importance_trigger_max": 150,
        "importance_trigger_curr": 150,
        "importance_ele_n": 0,
        "thought_count": 5,
        "daily_req": [],
        "f_daily_schedule": [],
        "f_daily_schedule_hourly_org": [],
        "act_address": None,
        "act_start_time": None,
        "act_duration": None,
        "act_description": None,
        "act_pronunciatio": None,
        "act_event": [name, None, None],
        "act_obj_description": None,
        "act_obj_pronunciatio": None,
        "act_obj_event": [None, None, None],
        "chatting_with": None,
        "chat": None,
        "chatting_with_buffer": {},
        "chatting_end_time": None,
        "act_path_set": False,
        "planned_path": [],
    }


def make_spatial_memory():
    """Return a world-knowledge dict covering all barangay locations."""
    world = {}
    seen_sectors = {}
    for zone_addr, objects in ZONE_MAP.values():
        parts = zone_addr.split(":")
        # parts: [world, sector, arena]
        w, sector, arena = parts[0], parts[1], parts[2]
        if sector not in seen_sectors:
            seen_sectors[sector] = {}
        seen_sectors[sector][arena] = objects
    world[WORLD_NAME] = seen_sectors
    return world


def make_empty_associative_memory():
    return {"nodes": {}, "seq_event": [], "seq_thought": [], "seq_chat": []}


def write_persona(name, scratch, spatial, assoc_mem, storage_root, sim_name):
    persona_dir = os.path.join(storage_root, sim_name, "personas", name, "bootstrap_memory")
    assoc_dir   = os.path.join(persona_dir, "associative_memory")
    os.makedirs(assoc_dir, exist_ok=True)

    with open(os.path.join(persona_dir, "scratch.json"), "w") as f:
        json.dump(scratch, f, indent=2)

    with open(os.path.join(persona_dir, "spatial_memory.json"), "w") as f:
        json.dump(spatial, f, indent=2)

    with open(os.path.join(assoc_dir, "nodes.json"), "w") as f:
        json.dump({}, f)

    with open(os.path.join(assoc_dir, "embeddings.json"), "w") as f:
        json.dump({}, f)

    with open(os.path.join(assoc_dir, "kw_strength.json"), "w") as f:
        json.dump({"kw_to_event": {}, "kw_to_thought": {}}, f)


def write_meta(storage_root, sim_name, agent_names):
    """Write the sim meta.json listing all persona names."""
    meta_dir = os.path.join(storage_root, sim_name)
    os.makedirs(meta_dir, exist_ok=True)
    meta = {
        "curr_time": "February 13, 2024, 07:00:00",
        "sec_per_step": 10,
        "maze_name": "barangay",
        "persona_names": agent_names,
        "step": 0,
    }
    with open(os.path.join(meta_dir, "reverie", "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    # Also write movement placeholder
    move_dir = os.path.join(meta_dir, "movement")
    os.makedirs(move_dir, exist_ok=True)
    with open(os.path.join(move_dir, "0.json"), "w") as f:
        json.dump({"persona": {}, "meta": {"curr_time": "February 13, 2024, 07:00:00"}}, f)


def main():
    parser = argparse.ArgumentParser(description="Initialize barangay personas")
    parser.add_argument("--roles", choices=["key", "all"], default="key",
                        help="'key' = political+enforcement only; 'all' = full 2716 agents")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to barangay_agents.csv")
    parser.add_argument("--sim", default="base_barangay", help="Simulation storage name")
    args = parser.parse_args()

    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), args.csv))
    storage_root = os.path.abspath(os.path.join(os.path.dirname(__file__), STORAGE_ROOT))

    print(f"Reading agents from: {csv_path}")
    print(f"Writing to: {storage_root}/{args.sim}")

    spatial = make_spatial_memory()
    agent_names = []
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            role = row["role"]
            if args.roles == "key" and role not in KEY_ROLES:
                skipped += 1
                continue

            name = row["name"].strip()
            scratch  = make_scratch(row)
            assoc    = make_empty_associative_memory()
            write_persona(name, scratch, spatial, assoc, storage_root, args.sim)
            agent_names.append(name)

    # Write reverie meta
    reverie_meta_dir = os.path.join(storage_root, args.sim, "reverie")
    os.makedirs(reverie_meta_dir, exist_ok=True)
    meta = {
        "curr_time": "February 13, 2024, 07:00:00",
        "sec_per_step": 10,
        "maze_name": "barangay",
        "persona_names": agent_names,
        "step": 0,
    }
    with open(os.path.join(reverie_meta_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    move_dir = os.path.join(storage_root, args.sim, "movement")
    os.makedirs(move_dir, exist_ok=True)
    with open(os.path.join(move_dir, "0.json"), "w") as f:
        json.dump({"persona": {n: {"movement": [0, 0], "pronunciatio": "💬",
                                   "description": "idle", "chat": None}
                               for n in agent_names},
                   "meta": {"curr_time": "February 13, 2024, 07:00:00"}}, f)

    print(f"\nInitialized {len(agent_names)} personas (skipped {skipped}).")
    print("Agent names written to meta.json.")
    if args.roles == "key":
        print("Run with --roles all to initialize all 2716 agents.")


if __name__ == "__main__":
    main()
