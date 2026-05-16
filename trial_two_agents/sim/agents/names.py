"""
agents/names.py
Filipino name pool for generating realistic agent names.
"""

import random

FIRST_NAMES_MALE = [
    "Pedro","Jose","Juan","Carlos","Ramon","Berto","Tony","Rodel","Dante",
    "Eduardo","Fernando","Gregorio","Hernando","Isidro","Jaime","Lando",
    "Manny","Noel","Oscar","Pablo","Quirino","Ricardo","Salvador","Tomas",
    "Ulysses","Vicente","Willy","Xavier","Yohan","Zaldy","Rolando","Efren",
    "Joselito","Renato","Alfredo","Bernardo","Crisanto","Diosdado","Ernesto",
]

FIRST_NAMES_FEMALE = [
    "Maria","Rosa","Ana","Nena","Lita","Cely","Fely","Teresita","Corazon",
    "Dolores","Esperanza","Florencia","Gloria","Herminia","Imelda","Josefa",
    "Ligaya","Milagros","Natividad","Ofelia","Pacita","Remedios","Socorro",
    "Trinidad","Urduja","Violeta","Wilhelmina","Ximena","Yolanda","Zenaida",
    "Maribel","Luzviminda","Annaliza","Cristina","Daisy","Elvira","Felicitas",
]

SURNAMES = [
    "Reyes","Cruz","Santos","Garcia","Lopez","Dela Cruz","Bautista","Ramos",
    "Gonzales","Flores","Villanueva","Castro","Aquino","Mendoza","Torres",
    "Aguilar","Hernandez","Soriano","Dizon","Lim","Tan","Sy","Co","Ong",
    "Manalo","Pascual","Ocampo","Guevarra","Valdez","Navarro","Magno",
    "Salazar","Domingo","Padilla","Mercado","Ferrer","Macaraeg","Tolentino",
    "Espiritu","Bonifacio","Rizal","Luna","Mabini","Jacinto","Gregorio",
]

# Political family names used for dynasty simulation
DYNASTY_FAMILIES = [
    "Reyes", "Villanueva", "Aquino", "Lim", "Garcia",
    "Santos", "Manalo", "Magno", "Ocampo", "Valdez",
]


def random_name(role: str = "") -> str:
    """
    Generate a random Filipino name.
    Some roles bias toward male/female names based on Philippine demographics.
    """
    female_biased = {"nurse", "teacher", "homemaker"}
    male_biased   = {"mayor", "contractor", "police", "farmer", "councilor"}

    r = random.random()
    if role in female_biased:
        use_female = r < 0.75
    elif role in male_biased:
        use_female = r < 0.25
    else:
        use_female = r < 0.50

    first = random.choice(FIRST_NAMES_FEMALE if use_female else FIRST_NAMES_MALE)
    last  = random.choice(SURNAMES)
    return f"{first} {last}"


def assign_family_ids(agents: list, num_families: int = 3,
                      dynasty_enabled: bool = True) -> dict:
    """
    Assign family_id to political agents in the dynasty environment.
    Returns a mapping of agent_id → family_id.
    Non-dynasty environment: no political family IDs assigned.

    In dynasty mode:
    - Mayor + some councilors share a family
    - Vice mayor may share with mayor or be from another family
    - Contractors linked to political families get same family_id
    """
    from .roles import Mayor, ViceMayor, Councilor, BarangayCaptain, Contractor

    assignments = {}
    if not dynasty_enabled:
        return assignments

    # Pick family names
    families = random.sample(DYNASTY_FAMILIES, min(num_families, len(DYNASTY_FAMILIES)))

    political = [a for a in agents
                 if isinstance(a, (Mayor, ViceMayor, Councilor, BarangayCaptain))]
    contractors = [a for a in agents if isinstance(a, Contractor)]

    if not political:
        return assignments

    # Dominant family gets mayor + 2-3 councilors
    dominant = families[0]
    mayor_agents = [a for a in political if isinstance(a, Mayor)]
    for a in mayor_agents:
        assignments[a.unique_id] = dominant
        a.family_id = dominant

    councilors = [a for a in political if isinstance(a, Councilor)]
    dynasty_councilor_count = random.randint(2, min(4, len(councilors)))
    for a in random.sample(councilors, dynasty_councilor_count):
        assignments[a.unique_id] = dominant
        a.family_id = dominant

    # Vice mayor: 60% chance same family as mayor
    for a in [a for a in political if isinstance(a, ViceMayor)]:
        fid = dominant if random.random() < 0.60 else (
            random.choice(families[1:]) if len(families) > 1 else None
        )
        if fid:
            assignments[a.unique_id] = fid
            a.family_id = fid

    # Secondary families get remaining councilors/captains
    remaining = [a for a in political if a.unique_id not in assignments]
    for i, a in enumerate(remaining):
        if len(families) > 1:
            fid = families[1 + (i % (len(families) - 1))]
            assignments[a.unique_id] = fid
            a.family_id = fid

    # 2 contractors linked to dominant family
    for a in random.sample(contractors, min(2, len(contractors))):
        assignments[a.unique_id] = dominant
        a.family_id = dominant

    return assignments
