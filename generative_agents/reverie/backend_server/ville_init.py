"""
ville_init.py — bootstrap 1000 barangay agents into the_ville world.

Reads barangay_agents_qc_1000_final-1.csv for identities/roles,
copies the_ville spatial memory, and places agents on the_ville tile grid.
Result: base_ville_1000 storage dir ready to fork from in reverie.py.
"""
import csv, json, os, shutil, itertools

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CSV_PATH    = "/home/student/197/barangay_agents_qc_1000_final-1.csv"
VILLE_BASE  = "/home/student/222/generative_agents/environment/frontend_server/storage/base_the_ville_n25"
OUT_BASE    = "/home/student/197/generative_agents/environment/frontend_server/storage/base_ville_1000"
STORAGE_ROOT = OUT_BASE  # alias used below

# ---------------------------------------------------------------------------
# KEY_ROLES — Tier-1 agents (same set as barangay_init.py)
# ---------------------------------------------------------------------------
KEY_ROLES = {
    "mayor", "vice_mayor", "councilor",
    "barangay_captain", "barangay_kagawad",
    "barangay_treasurer", "barangay_secretary",
    "municipal_engineer", "municipal_budget_officer", "municipal_treasurer",
    "procurement_officer", "business_permit_officer",
    "coa_auditor", "local_journalist", "cso_organizer", "social_welfare_officer",
    "police_officer",
    "local_elite_political_patron", "contractor_owner", "lawyer",
    "disaster_officer",
    "civil_servant_admin", "clerk_office_worker",
    "business_owner", "market_stall_owner", "market_vendor", "sari_sari_store_owner",
    "private_sector_manager",
}

# ---------------------------------------------------------------------------
# Load the_ville spatial memory (same for all agents)
# ---------------------------------------------------------------------------
sm_path = os.path.join(VILLE_BASE, "personas", "Abigail Chen",
                       "bootstrap_memory", "spatial_memory.json")
with open(sm_path) as f:
    VILLE_SPATIAL_MEM = json.load(f)

# Living areas: use the 25 real the_ville rooms (confirmed valid in spatial tree)
LIVING_AREAS = [
    "the Ville:artist's co-living space:Abigail Chen's room",
    "the Ville:Adam Smith's house:main room",
    "the Ville:Arthur Burton's apartment:main room",
    "the Ville:Dorm for Oak Hill College:Ayesha Khan's room",
    "the Ville:Carlos Gomez's apartment:main room",
    "the Ville:Tamara Taylor and Carmen Ortiz's house:Carmen Ortiz's room",
    "the Ville:Lin family's house:Eddy Lin's bedroom",
    "the Ville:artist's co-living space:Francisco Lopez's room",
    "the Ville:Giorgio Rossi's apartment:main room",
    "the Ville:artist's co-living space:Hailey Johnson's room",
    "the Ville:Isabella Rodriguez's apartment:main room",
    "the Ville:Moreno family's house:Tom and Jane Moreno's bedroom",
    "the Ville:Moore family's house:main room",
    "the Ville:Lin family's house:Mei and John Lin's bedroom",
    "the Ville:Dorm for Oak Hill College:Klaus Mueller's room",
    "the Ville:artist's co-living space:Latoya Williams's room",
    "the Ville:Dorm for Oak Hill College:Maria Lopez's room",
    "the Ville:artist's co-living space:Rajiv Patel's room",
    "the Ville:Ryan Park's apartment:main room",
    "the Ville:Tamara Taylor and Carmen Ortiz's house:Tamara Taylor's room",
    "the Ville:Dorm for Oak Hill College:Wolfgang Schulz's room",
    "the Ville:Yuriko Yamamoto's house:main room",
]
living_cycle = itertools.cycle(LIVING_AREAS)

# ---------------------------------------------------------------------------
# Spawn positions: use the 25 known-good the_ville positions, cycled
# ---------------------------------------------------------------------------
VILLE_SPAWNS = [
    (16,18),(26,18),(36,18),(16,32),(26,32),(53,14),(65,19),(72,14),(86,18),(94,18),
    (126,46),(123,57),(118,61),(107,62),(90,74),(91,74),(93,74),(72,74),(73,74),
    (54,74),(57,74),(20,65),(28,65),(36,65),(37,65),
]
spawn_positions = VILLE_SPAWNS

# ---------------------------------------------------------------------------
# Helper: derive personality string from numeric CSV traits
# ---------------------------------------------------------------------------
def make_innate(row):
    traits = []
    if float(row.get("integrity", 0.5)) > 0.65:
        traits.append("principled")
    elif float(row.get("integrity", 0.5)) < 0.35:
        traits.append("self-serving")
    if float(row.get("empathy", 0.5)) > 0.65:
        traits.append("empathetic")
    if float(row.get("ambition", 0.5)) > 0.65:
        traits.append("ambitious")
    elif float(row.get("ambition", 0.5)) < 0.35:
        traits.append("passive")
    if float(row.get("family_loyalty", 0.5)) > 0.65:
        traits.append("family-oriented")
    if float(row.get("greed", 0.5)) > 0.65:
        traits.append("opportunistic")
    if float(row.get("competence", 0.5)) > 0.65:
        traits.append("competent")
    if not traits:
        traits = ["practical", "reserved"]
    return ", ".join(traits[:4])

EDUCATION_MAP = {"1": "elementary", "2": "high school", "3": "college",
                 "4": "college", "5": "graduate"}
SOCIAL_LIFESTYLE = {
    "upper":  "goes to bed around 11pm, wakes up around 7am, eats dinner around 7pm.",
    "middle": "goes to bed around 10pm, wakes up around 6am, eats dinner around 6pm.",
    "lower":  "goes to bed around 9pm, wakes up around 5am, eats dinner around 5pm.",
}

def make_scratch(row, living_area, spawn_xy):
    name = row["name"].strip()
    parts = name.split()
    first = parts[0]
    last  = parts[-1] if len(parts) > 1 else parts[0]
    role  = row["role"].strip()
    edu   = EDUCATION_MAP.get(row.get("education_level", "2"), "high school")
    sc    = row.get("social_class", "middle").strip().lower()
    goals = row.get("goals", "").strip()
    tier  = 1 if role in KEY_ROLES else 2

    learned = (f"{name} is a {role.replace('_',' ')} with a {edu} education. "
               f"They come from a {sc}-class background in the community.")
    currently = goals.split("|")[0].strip() if goals else f"{name} is managing daily responsibilities."
    lifestyle = f"{name} {SOCIAL_LIFESTYLE.get(sc, SOCIAL_LIFESTYLE['middle'])}"

    return {
        "vision_r": 8,
        "att_bandwidth": 8,
        "retention": 8,
        "curr_time": None,
        "curr_tile": list(spawn_xy),
        "daily_plan_req": "",
        "name": name,
        "first_name": first,
        "last_name": last,
        "age": int(float(row.get("age", 30))),
        "innate": make_innate(row),
        "learned": learned,
        "currently": currently,
        "lifestyle": lifestyle,
        "living_area": living_area,
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
        "importance_trigger_max": 250,
        "importance_trigger_curr": 250,
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
        # Barangay-specific fields for tier routing
        "agent_tier": tier,
        "role": role,
        "reflect_prob": round(float(row.get("competence", 0.5)) * 0.1, 4),
        "last_reflect_time": None,
        "family_id": row.get("family_id", ""),
    }

# ---------------------------------------------------------------------------
# Main bootstrap
# ---------------------------------------------------------------------------
if os.path.exists(OUT_BASE):
    shutil.rmtree(OUT_BASE)
os.makedirs(OUT_BASE)

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    rows = [r for r in csv.DictReader(f) if r.get("is_alive", "TRUE").upper() == "TRUE"]

rows = rows[:1000]
persona_names = []
env_positions = {}

for i, row in enumerate(rows):
    name = row["name"].strip()
    persona_names.append(name)
    spawn = spawn_positions[i % len(spawn_positions)]
    living_area = next(living_cycle)

    # Directory structure
    persona_dir = os.path.join(OUT_BASE, "personas", name, "bootstrap_memory")
    assoc_dir   = os.path.join(persona_dir, "associative_memory")
    os.makedirs(assoc_dir, exist_ok=True)

    with open(os.path.join(persona_dir, "scratch.json"), "w") as f:
        json.dump(make_scratch(row, living_area, spawn), f, indent=2)

    with open(os.path.join(persona_dir, "spatial_memory.json"), "w") as f:
        json.dump(VILLE_SPATIAL_MEM, f, indent=2)

    for fname, content in [("nodes.json", {}),
                            ("embeddings.json", {}),
                            ("kw_strength.json", {"kw_strength_event": {}, "kw_strength_thought": {}})]:
        with open(os.path.join(assoc_dir, fname), "w") as f:
            json.dump(content, f)

    env_positions[name] = {"x": spawn[0], "y": spawn[1]}

# movement/ dir (reverie.py writes here each step)
os.makedirs(os.path.join(OUT_BASE, "movement"), exist_ok=True)

# environment/0.json
env_dir = os.path.join(OUT_BASE, "environment")
os.makedirs(env_dir, exist_ok=True)
with open(os.path.join(env_dir, "0.json"), "w") as f:
    json.dump(env_positions, f, indent=2)

# reverie/meta.json
rev_dir = os.path.join(OUT_BASE, "reverie")
os.makedirs(rev_dir, exist_ok=True)
meta = {
    "fork_sim_code": "base_ville_1000",
    "start_date": "February 13, 2023",
    "curr_time": "February 13, 2023, 00:00:00",
    "sec_per_step": 3600,
    "maze_name": "the_ville",
    "persona_names": persona_names,
    "step": 0,
}
with open(os.path.join(rev_dir, "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

t1 = sum(1 for r in rows if r["role"].strip() in KEY_ROLES)
print(f"Created base_ville_1000: {len(persona_names)} agents ({t1} Tier-1, {len(persona_names)-t1} Tier-2)")
print(f"Spawn grid: {len(spawn_positions)} available positions")
print(f"Output: {OUT_BASE}")
