"""
agent_creation.py
Generates barangay_agents.csv — the canonical 1000-agent roster
for Mabuhay Province simulation (2020-2026).

Usage:
    python agent_creation.py                      # dynasty scenario (default)
    python agent_creation.py --no-dynasty         # competitive/reform seed
    python agent_creation.py --seed 99
    python agent_creation.py --output my_agents.csv

Economic distribution (mirrors PSA 2021 FIES for Philippine province):
    A  elite        ~0.4%   ₱3M-₱20M wealth    (governor, spouse, elite children)
    B  upper        ~2.4%   ₱500K-₱3M           (officials, contractors)
    C  middle       ~6.5%   ₱80K-₱500K          (councilors, professionals)
    D  lower-mid   ~27.2%   ₱15K-₱80K           (teachers, nurses, vendors)
    E  poor        ~63.5%   ₱500-₱15K           (farmers, informal, students)

Dynasty family (24 members, Philippine Civil Code Articles 963-967):
    0°  ego (Governor)
    1°  consanguinity: sons, daughters, parents
    1°  affinity:      spouse, in-laws
    2°  consanguinity: siblings, grandparents
    2°  affinity:      siblings-in-law
    3°  consanguinity: nephews/nieces, uncles/aunts
    3°  affinity:      nephews/nieces-in-law
    4°  consanguinity: first cousins
    4°  affinity:      first cousins-in-law
"""

import argparse
import csv
import random
from dataclasses import dataclass
from typing import List, Optional


# ── Name pools ────────────────────────────────────────────────────────────────

FIRST_NAMES_MALE = [
    "Pedro","Jose","Juan","Carlos","Ramon","Berto","Tony","Rodel","Dante",
    "Eduardo","Fernando","Gregorio","Hernando","Isidro","Jaime","Lando",
    "Manny","Noel","Oscar","Pablo","Quirino","Ricardo","Salvador","Tomas",
    "Ulysses","Vicente","Willy","Rolando","Efren","Joselito","Renato",
    "Alfredo","Bernardo","Crisanto","Diosdado","Ernesto","Francisco","Gilberto",
    "Honorio","Ignacio","Juanito","Leopoldo","Marcelino","Nicanor","Onofre",
]

FIRST_NAMES_FEMALE = [
    "Maria","Rosa","Ana","Nena","Lita","Cely","Fely","Teresita","Corazon",
    "Dolores","Esperanza","Florencia","Gloria","Herminia","Imelda","Josefa",
    "Ligaya","Milagros","Natividad","Ofelia","Pacita","Remedios","Socorro",
    "Trinidad","Urduja","Violeta","Maribel","Luzviminda","Annaliza","Cristina",
    "Daisy","Elvira","Felicitas","Gertrudes","Hipolita","Isadora","Juliana",
    "Kathrina","Leonora","Margarita","Norma","Perla","Quirina","Rosalinda",
]

SURNAMES = [
    "Reyes","Cruz","Santos","Garcia","Lopez","Dela Cruz","Bautista","Ramos",
    "Gonzales","Flores","Villanueva","Castro","Aquino","Mendoza","Torres",
    "Aguilar","Hernandez","Soriano","Dizon","Lim","Tan","Sy","Co","Ong",
    "Manalo","Pascual","Ocampo","Guevarra","Valdez","Navarro","Magno",
    "Salazar","Domingo","Padilla","Mercado","Ferrer","Macaraeg","Tolentino",
    "Espiritu","Bonifacio","Luna","Mabini","Jacinto","Gregorio","Ilagan",
    "Buenaventura","Dimalanta","Enriquez","Fajardo","Gatchalian","Hidalgo",
]

# Plausible Philippine political dynasty surnames
DYNASTY_SURNAMES = [
    "Reyes","Villanueva","Aquino","Lim","Garcia",
    "Santos","Manalo","Magno","Ocampo","Valdez",
    "Tatlonghari","Estrada","Macapagal","Marcos","Arroyo",
]


# ── Economic class definitions ────────────────────────────────────────────────

CLASS_ORDER = ["A", "B", "C", "D", "E"]

WEALTH_RANGE = {
    "A": (3_000_000, 20_000_000),  # elite / political class
    "B": (500_000,    3_000_000),  # upper / officials
    "C": (80_000,      500_000),   # middle / professionals
    "D": (15_000,       80_000),   # lower-middle
    "E": (500,          15_000),   # poor / majority
}

INCOME_RANGE = {                   # daily income in pesos
    "A": (5_000, 20_000),
    "B": (1_500,  5_000),
    "C": (500,    1_500),
    "D": (200,      500),
    "E": (0,        200),
}

# Base economic class per role (non-dynasty)
ROLE_BASE_CLASS = {
    "governor":         "A",
    "vice_governor":    "A",
    "board_member":     "B",
    "mayor":            "B",
    "vice_mayor":       "B",
    "councilor":        "C",
    "barangay_captain": "C",
    "contractor":       "B",
    "business_owner":   "C",
    "teacher":          "D",
    "nurse":            "D",
    "police":           "D",
    "journalist":       "C",
    "auditor":          "C",
    "vendor":           "D",
    "farmer":           "E",
    "informal_worker":  "E",
    "student":          "E",
    "unemployed":       "E",
    "elder":            "D",
}


# ── Trait biases ──────────────────────────────────────────────────────────────

ROLE_TRAIT_BIAS = {
    "governor":         {"ambition": 0.80, "competence": 0.65, "family_loyalty": 0.70},
    "vice_governor":    {"integrity": 0.58, "ambition": 0.70},
    "board_member":     {"ambition": 0.60},
    "mayor":            {"ambition": 0.75, "competence": 0.65},
    "vice_mayor":       {"integrity": 0.60, "competence": 0.60},
    "councilor":        {"ambition": 0.60},
    "barangay_captain": {"family_loyalty": 0.65},
    "contractor":       {"greed": 0.70, "ambition": 0.65},
    "business_owner":   {"ambition": 0.60, "competence": 0.60},
    "teacher":          {"integrity": 0.65, "empathy": 0.70},
    "nurse":            {"empathy": 0.75, "integrity": 0.65},
    "police":           {"integrity": 0.50, "greed": 0.50},
    "journalist":       {"integrity": 0.70, "ambition": 0.60},
    "auditor":          {"integrity": 0.75, "competence": 0.65},
    "vendor":           {"empathy": 0.55, "integrity": 0.55},
    "farmer":           {"integrity": 0.60, "family_loyalty": 0.70},
    "informal_worker":  {"empathy": 0.55},
    "student":          {"empathy": 0.60, "ambition": 0.55},
    "unemployed":       {"greed": 0.55},
    "elder":            {"integrity": 0.65, "family_loyalty": 0.70},
}


# ── Demographics ──────────────────────────────────────────────────────────────

ROLE_AGE_RANGE = {
    "governor":         (40, 75),
    "vice_governor":    (35, 70),
    "board_member":     (28, 70),
    "mayor":            (35, 75),
    "vice_mayor":       (30, 70),
    "councilor":        (28, 70),
    "barangay_captain": (28, 70),
    "student":          (6,  24),
    "elder":            (60, 90),
}
DEFAULT_AGE_RANGE = (18, 65)

ROLE_EDUCATION_RANGE = {
    "governor":         (4, 5),
    "vice_governor":    (4, 5),
    "board_member":     (3, 5),
    "mayor":            (4, 5),
    "vice_mayor":       (4, 5),
    "councilor":        (3, 5),
    "teacher":          (4, 5),
    "nurse":            (4, 5),
    "auditor":          (4, 5),
    "journalist":       (3, 5),
    "contractor":       (3, 5),
    "student":          (1, 4),
    "farmer":           (1, 3),
    "informal_worker":  (1, 3),
    "unemployed":       (1, 3),
    "elder":            (1, 4),
}
DEFAULT_EDUCATION_RANGE = (2, 4)

# (preferred_sex, probability)
ROLE_SEX_BIAS = {
    "governor":         ("M", 0.82),
    "vice_governor":    ("F", 0.60),
    "board_member":     ("M", 0.65),
    "mayor":            ("M", 0.80),
    "vice_mayor":       ("M", 0.72),
    "councilor":        ("M", 0.70),
    "barangay_captain": ("M", 0.75),
    "contractor":       ("M", 0.85),
    "police":           ("M", 0.82),
    "farmer":           ("M", 0.72),
    "nurse":            ("F", 0.82),
    "teacher":          ("F", 0.70),
    "journalist":       ("F", 0.55),
    "vendor":           ("F", 0.62),
    "business_owner":   ("M", 0.55),
}


# ── Role distribution (1000 agents total) ────────────────────────────────────

ROLE_DISTRIBUTION = {
    # Provincial government (12)
    "governor":         1,
    "vice_governor":    1,
    "board_member":     10,
    # Municipal government (33)
    "mayor":            3,
    "vice_mayor":       3,
    "councilor":        24,
    "barangay_captain": 8,
    # Business (113)
    "contractor":       8,
    "vendor":           80,
    "business_owner":   25,
    # Civic workers (102)
    "teacher":          60,
    "nurse":            20,
    "police":           15,
    "journalist":       4,
    "auditor":          3,
    # Citizens (735)
    "farmer":           205,
    "informal_worker":  150,
    "student":          200,
    "unemployed":       80,
    "elder":            100,
}  # sum = 1000


# ── Dynasty family structure (24 members, 0°–4° civil degree) ────────────────
#
# Columns:
#   role, civil_degree, relation_type, relation_label, forced_sex, econ_class
#
# Consanguinity = blood relation (Philippine Civil Code Art. 963-967)
# Affinity      = relation by marriage (Art. 963 applied by analogy)
#
# Anti-dynasty laws count BOTH types equally up to 4th degree.

DYNASTY_FAMILY_STRUCTURE = [
    # ── 0° ──────────────────────────────────────────────────────────────────
    ("governor",         0, "consanguinity", "ego",                "M", "A"),
    # ── 1° consanguinity ────────────────────────────────────────────────────
    ("board_member",     1, "consanguinity", "son",                "M", "A"),
    ("board_member",     1, "consanguinity", "daughter",           "F", "A"),
    ("councilor",        1, "consanguinity", "son",                "M", "B"),
    ("elder",            1, "consanguinity", "father",             "M", "C"),
    ("elder",            1, "consanguinity", "mother",             "F", "C"),
    # ── 1° affinity ─────────────────────────────────────────────────────────
    ("vice_governor",    1, "affinity",      "spouse",             "F", "A"),
    ("contractor",       1, "affinity",      "son-in-law",         "M", "B"),
    # ── 2° consanguinity ────────────────────────────────────────────────────
    ("mayor",            2, "consanguinity", "brother",            "M", "B"),
    ("board_member",     2, "consanguinity", "sister",             "F", "B"),
    ("councilor",        2, "consanguinity", "brother",            "M", "B"),
    # ── 2° affinity ─────────────────────────────────────────────────────────
    ("vice_mayor",       2, "affinity",      "brother-in-law",     "M", "B"),
    ("business_owner",   2, "affinity",      "sister-in-law",      "F", "B"),
    # ── 3° consanguinity ────────────────────────────────────────────────────
    ("barangay_captain", 3, "consanguinity", "nephew",             "M", "C"),
    ("councilor",        3, "consanguinity", "nephew",             "M", "C"),
    ("teacher",          3, "consanguinity", "niece",              "F", "D"),
    ("elder",            3, "consanguinity", "uncle",              "M", "C"),
    # ── 3° affinity ─────────────────────────────────────────────────────────
    ("barangay_captain", 3, "affinity",      "nephew-in-law",      "M", "C"),
    ("journalist",       3, "affinity",      "niece-in-law",       "F", "C"),
    # ── 4° consanguinity ────────────────────────────────────────────────────
    ("councilor",        4, "consanguinity", "first-cousin",       "M", "C"),
    ("councilor",        4, "consanguinity", "first-cousin",       "F", "C"),
    ("barangay_captain", 4, "consanguinity", "first-cousin",       "M", "C"),
    ("contractor",       4, "consanguinity", "first-cousin",       "M", "C"),
    # ── 4° affinity ─────────────────────────────────────────────────────────
    ("business_owner",   4, "affinity",      "first-cousin-in-law","F", "C"),
]  # 24 members


# ── Goals by role ─────────────────────────────────────────────────────────────

ROLE_GOALS = {
    "governor":         "Win re-election | Consolidate family dynasty | Deliver infrastructure | Grow family wealth",
    "vice_governor":    "Preside Sangguniang Panlalawigan | Position for governor race | Shield family from scrutiny",
    "board_member":     "Pass provincial ordinance | Support governor agenda | Secure contractor patronage",
    "mayor":            "Win re-election | Build road projects | Fund school renovation | Increase family wealth",
    "vice_mayor":       "Audit contracts | Position for mayor | Build political base",
    "councilor":        "Pass budget bill | Expose corruption | Secure contractor support",
    "barangay_captain": "Distribute aid fairly | Resolve local disputes | Skim aid for family",
    "contractor":       "Win public works contract | Bill for incomplete projects | Bribe officials",
    "business_owner":   "Grow business revenue | Secure permits | Expand market share",
    "teacher":          "Deliver quality lessons | Resist political pressure | Secure school funding",
    "nurse":            "Treat patients | Report supply shortages | Advocate for hospital budget",
    "police":           "Enforce the law | Investigate crimes | Accept bribe to ignore violations",
    "journalist":       "Publish corruption story | Investigate ghost projects | Resist media suppression",
    "auditor":          "Flag budget discrepancies | Expose overpayments | Bury inconvenient findings",
    "vendor":           "Earn enough for the day | Pay for child education | Resist market extortion",
    "farmer":           "Achieve good harvest | Fix irrigation access | Educate children | Join cooperative",
    "informal_worker":  "Find stable work today | Feed family | Avoid eviction",
    "student":          "Finish school year | Qualify for scholarship | Join civic movement",
    "unemployed":       "Find employment | Accept patronage offer | Feed family",
    "elder":            "Receive pension on time | Vote wisely | See family succeed",
}


# ── Location mapping ──────────────────────────────────────────────────────────

ROLE_HOME_ZONE = {
    "governor":"resA","vice_governor":"resA","board_member":"resA",
    "mayor":"resA","vice_mayor":"resA","councilor":"resA",
    "contractor":"resA","auditor":"resA",
    "business_owner":"resB","teacher":"resB","nurse":"resB",
    "police":"resB","journalist":"resB","student":"resB",
    "barangay_captain":"resB","elder":"resA",
    "vendor":"resC","farmer":"resC","informal_worker":"resC","unemployed":"resC",
}

ROLE_WORK_ZONE = {
    "governor":"capitol","vice_governor":"capitol","board_member":"capitol",
    "mayor":"munhall","vice_mayor":"munhall","councilor":"munhall",
    "barangay_captain":"bgyhall","contractor":"contoffice",
    "vendor":"market","business_owner":"market","teacher":"school",
    "nurse":"prv_hosp","police":"police","journalist":"media",
    "auditor":"audit","farmer":"farm","informal_worker":"market",
    "student":"school","unemployed":"park","elder":"church",
}


# ── Core helpers ──────────────────────────────────────────────────────────────

@dataclass
class Traits:
    integrity:      float
    greed:          float
    ambition:       float
    family_loyalty: float
    competence:     float
    empathy:        float

    @classmethod
    def random(cls, bias: dict = None):
        bias = bias or {}
        def v(k):
            return round(max(0.0, min(1.0, random.gauss(bias.get(k, 0.5), 0.15))), 3)
        return cls(
            integrity=v("integrity"), greed=v("greed"), ambition=v("ambition"),
            family_loyalty=v("family_loyalty"), competence=v("competence"),
            empathy=v("empathy"),
        )


def _sex(role: str, forced: Optional[str] = None) -> str:
    if forced:
        return forced
    if role in ROLE_SEX_BIAS:
        preferred, prob = ROLE_SEX_BIAS[role]
        return preferred if random.random() < prob else ("F" if preferred == "M" else "M")
    return random.choice(["M", "F"])


def _name(sex: str, surname: str = None) -> str:
    pool  = FIRST_NAMES_FEMALE if sex == "F" else FIRST_NAMES_MALE
    first = random.choice(pool)
    last  = surname or random.choice(SURNAMES)
    return f"{first} {last}"


def _age(role: str) -> int:
    lo, hi = ROLE_AGE_RANGE.get(role, DEFAULT_AGE_RANGE)
    return random.randint(lo, hi)


def _education(role: str) -> int:
    lo, hi = ROLE_EDUCATION_RANGE.get(role, DEFAULT_EDUCATION_RANGE)
    return random.randint(lo, hi)


def _wealth(cls: str) -> float:
    lo, hi = WEALTH_RANGE[cls]
    return round(random.uniform(lo, hi), 2)


def _income(cls: str) -> float:
    lo, hi = INCOME_RANGE[cls]
    return round(random.uniform(lo, hi), 2)


def _make_agent(
    agent_id:      int,
    role:          str,
    econ_class:    str,
    surname:       Optional[str] = None,
    forced_sex:    Optional[str] = None,
    family_id:     str = "",
    civil_degree:  Optional[int] = None,
    relation_type: str = "",
    relation_label:str = "",
) -> dict:
    sex    = _sex(role, forced_sex)
    traits = Traits.random(ROLE_TRAIT_BIAS.get(role, {}))
    trust  = round(
        random.uniform(0.75, 1.0) if family_id else random.uniform(-0.1, 0.2), 3
    )
    return {
        "agent_id":           agent_id,
        "name":               _name(sex, surname),
        "sex":                sex,
        "age":                _age(role),
        "education_level":    _education(role),
        "role":               role,
        "family_id":          family_id,
        "civil_degree":       civil_degree if civil_degree is not None else "",
        "relation_type":      relation_type,
        "relation_label":     relation_label,
        "home_zone":          ROLE_HOME_ZONE.get(role, "resC"),
        "work_zone":          ROLE_WORK_ZONE.get(role, "market"),
        "social_class":       econ_class,
        "wealth":             _wealth(econ_class),
        "income_per_day":     _income(econ_class),
        "satisfaction":       round(random.uniform(35, 75), 2),
        "goals":              ROLE_GOALS.get(role, "Improve household welfare"),
        "is_alive":           True,
        "integrity":          traits.integrity,
        "greed":              traits.greed,
        "ambition":           traits.ambition,
        "family_loyalty":     traits.family_loyalty,
        "competence":         traits.competence,
        "empathy":            traits.empathy,
        "initial_trust_score":trust,
    }


# ── Generation ────────────────────────────────────────────────────────────────

def generate_agents(dynasty_enabled: bool = True, seed: int = 42) -> List[dict]:
    random.seed(seed)

    agents:      List[dict] = []
    role_filled: dict       = {r: 0 for r in ROLE_DISTRIBUTION}
    agent_id = 1

    # ── Step 1: dynasty family (24 members with civil-degree structure) ───
    dynasty_surname = random.choice(DYNASTY_SURNAMES)

    if dynasty_enabled:
        for (role, degree, rel_type, rel_label, forced_sex, econ_cls) in DYNASTY_FAMILY_STRUCTURE:
            if role not in ROLE_DISTRIBUTION:
                continue
            # Blood relatives share the dynasty surname;
            # affinity relatives (except spouse) bring their own.
            if rel_type == "consanguinity" or rel_label == "spouse":
                surname = dynasty_surname
            else:
                surname = random.choice([s for s in SURNAMES if s != dynasty_surname])

            agents.append(_make_agent(
                agent_id=agent_id, role=role, econ_class=econ_cls,
                surname=surname, forced_sex=forced_sex,
                family_id=dynasty_surname,
                civil_degree=degree, relation_type=rel_type, relation_label=rel_label,
            ))
            role_filled[role] = role_filled.get(role, 0) + 1
            agent_id += 1

    # ── Step 2: fill remaining slots (non-dynasty) ────────────────────────
    for role, total in ROLE_DISTRIBUTION.items():
        remaining = total - role_filled.get(role, 0)
        econ_cls  = ROLE_BASE_CLASS.get(role, "E")
        for _ in range(remaining):
            agents.append(_make_agent(
                agent_id=agent_id, role=role, econ_class=econ_cls,
            ))
            agent_id += 1

    return agents


# ── CSV output ────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "agent_id", "name", "sex", "age", "education_level",
    "role", "family_id", "civil_degree", "relation_type", "relation_label",
    "home_zone", "work_zone", "social_class",
    "wealth", "income_per_day", "satisfaction", "goals", "is_alive",
    "integrity", "greed", "ambition", "family_loyalty", "competence", "empathy",
    "initial_trust_score",
]


def write_csv(agents: List[dict], filename: str):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(agents)

    _print_summary(agents, filename)


def _print_summary(agents: List[dict], filename: str):
    from collections import Counter
    classes  = Counter(a["social_class"]  for a in agents)
    dyn      = [a for a in agents if a["family_id"]]
    dyn_name = dyn[0]["family_id"] if dyn else "N/A"

    print(f"\n{'='*55}")
    print(f"  Mabuhay Province — Agent Roster")
    print(f"{'='*55}")
    print(f"  File          : {filename}")
    print(f"  Total agents  : {len(agents)}")
    print(f"  Dynasty family: {len(dyn)} members  (surname: {dyn_name})")
    print(f"\n  Economic class distribution (PSA-aligned):")
    labels = {"A":"elite","B":"upper","C":"middle","D":"lower-mid","E":"poor"}
    for cls in CLASS_ORDER:
        n   = classes.get(cls, 0)
        pct = n / len(agents) * 100
        bar = "█" * max(1, int(pct / 2))
        print(f"    {cls} {labels[cls]:<10}: {n:4d}  ({pct:5.1f}%)  {bar}")

    if dyn:
        print(f"\n  Dynasty civil degrees:")
        deg_count = Counter(
            str(a["civil_degree"]) for a in dyn if a["civil_degree"] != ""
        )
        for deg in ["0","1","2","3","4"]:
            n = deg_count.get(deg, 0)
            if n:
                print(f"    {deg}°  {n} member{'s' if n>1 else ''}")

        print(f"\n  Dynasty roles:")
        dyn_roles = Counter(a["role"] for a in dyn)
        for role, n in sorted(dyn_roles.items()):
            print(f"    {role:<20} {n}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Mabuhay Province agent roster"
    )
    parser.add_argument("--no-dynasty", action="store_true",
                        help="No dynasty family (competitive/reform seed)")
    parser.add_argument("--seed",   type=int, default=42)
    parser.add_argument("--output", type=str, default="barangay_agents.csv")
    args = parser.parse_args()

    agents = generate_agents(dynasty_enabled=not args.no_dynasty, seed=args.seed)
    write_csv(agents, args.output)
