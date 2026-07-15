"""
barangay_patronage.py — how a dynasty actually holds a barangay: utang na loob.

Philippine dynasties persist less through fraud than through PERSONAL DEBT:
decades of paid hospital bills, funeral aid, fiesta sponsorships, jobs. The
client remembers who helped when nobody else would — and that memory votes.
This module makes that loyalty a first-class, memory-mediated mechanic:

  seed_patronage()  — ONE-TIME at fresh-sim start (marker-file guarded): every
    family holding 2+ seats (a true dynasty-in-power) gets a client base of
    poor residents — neighbors of its officials first — each carrying an
    "utang na loob" memory toward the family's most senior official, with
    poignancy scaled by the client's OWN family_loyalty trait. These classify
    as governance (personal gratitude), so they feed name_trust and votes.

  step_patronage()  — low-cadence tick (~every 4 sim-days): each dynasty
    official LLM-decides (Tier-1) whether to spend on clientelist favors right
    now. GRANT -> a handful of clients receive fresh personal-help memories
    (renewing the debt); a few tie-based witnesses read it as machine
    politics ("buying loyalty", corruption-classified, low poignancy).
    Deciding NOT to spend lets the debt decay — neglected clients drift.

Loyalty is therefore emergent and contestable: it decays with neglect, is
renewed by favors, resists spin-skepticism (gratitude is lived experience,
not news), and is outvoted only by stronger lived grievance.
"""
import os, re, random, datetime, logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from barangay_roles import OFFICIAL_ROLES

logger = logging.getLogger(__name__)

_INTERVAL     = int(os.environ.get("PATRONAGE_INTERVAL", 96))     # ~4 sim-days
_CLIENTS      = int(os.environ.get("CLIENTS_PER_DYNASTY", 40))
_FAVORS       = int(os.environ.get("PATRONAGE_FAVORS", 8))        # per official per GRANT
_MAX_WORKERS  = int(os.environ.get("DECISION_MAX_WORKERS", 16))
_TOKENS       = int(os.environ.get("PATRONAGE_TOKENS", 80))
_EXPIRE_DAYS  = int(os.environ.get("PATRONAGE_EXPIRE_DAYS", 90))  # debts outlive news

# LOYALTY LOOP GAIN — scales the poignancy of every loyalty-side injection
# (utang seeds, favors, mobilization reminders). 1.0 = calibrated default;
# sweep it (with GRIEVANCE_GAIN) to test how loop magnitude shifts outcomes.
_LOYALTY_GAIN = float(os.environ.get("LOYALTY_GAIN", 1.0))


def _poig(base):
    """Apply the loyalty-loop gain to a base poignancy, clamped to [1, 9]."""
    return max(1, min(9, round(base * _LOYALTY_GAIN)))

_DEBT_STORIES = [
    "paid the hospital bill when {who}'s mother was sick and nobody else would help",
    "covered the funeral costs when {who}'s family lost someone",
    "got {who}'s cousin a job at the municipal hall",
    "sponsored the fiesta and the basketball league in {who}'s street",
    "paid {who}'s child's school fees one bad year",
]
_FAVOR_STORIES = [
    "sent medicine when someone in the household got sick",
    "handed an envelope for the funeral, no questions asked",
    "fixed a job for a nephew at the hall",
    "covered the electric bill after the layoff",
    "sponsored the street fiesta again this year",
]


def _trait(row, key, default):
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _add_memory(persona, text, curr_time, poignancy, s, p, o, kw,
                expire_days=_EXPIRE_DAYS):
    """Inject one memory; SKIP (never zero-vector) if embedding fails.
    Patronage debts persist far longer than news — 90-day expiration."""
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        try:
            emb = get_embedding(text)
        except Exception as e:
            logger.warning(f"[PATRONAGE] embedding failed, memory skipped: {e}")
            return False
        expiration = curr_time + datetime.timedelta(days=expire_days)
        persona.a_mem.add_thought(curr_time, expiration, s, p, o,
                                  text, set(kw), poignancy, (text, emb), [])
        return True
    except Exception as e:
        logger.warning(f"[PATRONAGE] memory inject failed for "
                       f"{getattr(persona.scratch, 'name', '?')}: {e}")
        return False


def dynasty_seat_families(personas, rows):
    """family_id -> [official names], for families holding 2+ seats (live
    scratch roles — tracks elections). These are the dynasties-in-power."""
    fam = {}
    for n, p in personas.items():
        role = getattr(p.scratch, "role", rows.get(n, {}).get("role", ""))
        f = (rows.get(n, {}).get("family_id") or "").strip()
        if f and role in OFFICIAL_ROLES:
            fam.setdefault(f, []).append(n)
    return {f: names for f, names in fam.items() if len(names) >= 2}


def _patron_of(family_officials, rows):
    """The family's most senior seat = the patron clients feel indebted to."""
    order = ["mayor", "vice_mayor", "barangay_captain", "councilor",
             "barangay_kagawad"]
    def rank(n):
        r = rows.get(n, {}).get("role", "")
        return order.index(r) if r in order else len(order)
    return sorted(family_officials, key=rank)[0]


def _client_pool(fam, family_officials, personas, rows, k):
    """Clients: poor residents, neighbors of the family's officials first."""
    zones = {(rows.get(n, {}).get("home_zone") or "").strip()
             for n in family_officials}
    near, far = [], []
    for n in personas:
        r = rows.get(n, {})
        if (r.get("family_id") or "").strip() == fam:
            continue
        if r.get("role", "") in OFFICIAL_ROLES:
            continue
        if "lower" not in (r.get("social_class") or "").lower():
            continue
        ((r.get("home_zone") or "").strip() in zones and near or far).append(n)
    random.shuffle(near); random.shuffle(far)
    return (near + far)[:k]


def seed_patronage(personas, agent_rows, curr_time, sim_reverie_dir):
    """One-time client-base seeding for every dynasty-in-power (marker-file
    guarded so resumes don't re-seed). Returns clients seeded."""
    marker = os.path.join(sim_reverie_dir, "patronage_seeded")
    if os.path.exists(marker):
        return 0
    rows = {r["name"].strip(): r for r in agent_rows}
    dynasties = dynasty_seat_families(personas, rows)
    total = 0
    for fam, officials in dynasties.items():
        patron = _patron_of(officials, rows)
        for client in _client_pool(fam, officials, personas, rows, _CLIENTS):
            loyalty = _trait(rows.get(client, {}), "family_loyalty", 0.5)
            poig = _poig(5 + 3 * loyalty)
            story = random.choice(_DEBT_STORIES).format(who=client)
            text = (f"{client}'s family owes much to the {fam} family — "
                    f"{patron} {story}. Utang na loob is not forgotten.")
            if _add_memory(personas[client], text, curr_time, poig,
                           s=patron, p="helped", o=client,
                           kw={"service", "loyalty", "utang", patron, fam}):
                total += 1
    try:
        with open(marker, "w") as f:
            f.write(str(curr_time))
    except Exception:
        pass
    if total:
        print(f"[PATRONAGE] seeded {total} utang-na-loob client bonds across "
              f"{len(dynasties)} dynasties-in-power", flush=True)
    return total


def _decide_grant(name, persona, role, fam, row):
    """Does this official spend on the machine right now? Tier-1, in character."""
    from persona.prompt_template.gpt_structure import (
        ChatGPT_request, set_force_tier, clear_force_tier)
    greed = _trait(row, "greed", 0.4)
    amb   = _trait(row, "ambition", 0.5)
    mems = []
    try:
        from persona.cognitive_modules.converse import _salient_memories
        mems = _salient_memories(persona, k=4, window_hours=240)
    except Exception:
        pass
    mem_block = ("\n".join(f"- {m}" for m in mems)
                 if mems else "- (nothing weighing on you in particular)")
    prompt = (
f"""You are {name}, the barangay {role} of the {fam} political family. Stay fully in character.
Your nature: greed {greed:.2f}/1, ambition {amb:.2f}/1.
On your mind lately:
{mem_block}
The family's strength is the people who owe it: hospital bills, funerals, jobs, fiestas. Keeping that machine alive costs money and time, but a neglected client forgets.
Do you spend on favors for your people this week? Answer EXACTLY:
GRANT: YES or NO"""
    )
    try:
        set_force_tier(1)
        out = ChatGPT_request(prompt, max_tokens=_TOKENS)
    except Exception as e:
        logger.warning(f"[PATRONAGE] LLM failed for {name}: {e}")
        return False
    finally:
        clear_force_tier()
    return bool(out) and out != "ChatGPT ERROR" and \
        re.search(r"GRANT:\s*YES", out, re.I) is not None


def step_patronage(personas, agent_rows, curr_time):
    """One clientelism tick: each dynasty official decides whether to renew
    the machine. Returns (n_grants, n_favors)."""
    rows = {r["name"].strip(): r for r in agent_rows}
    dynasties = dynasty_seat_families(personas, rows)
    if not dynasties:
        return 0, 0

    officials = [(n, fam) for fam, names in dynasties.items() for n in names]
    decisions = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futs = {ex.submit(_decide_grant, n, personas[n],
                          rows.get(n, {}).get("role", "official"), fam,
                          rows.get(n, {})): n
                for n, fam in officials}
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                decisions[n] = fut.result()
            except Exception:
                decisions[n] = False

    n_grants = n_favors = 0
    for name, fam in officials:
        if not decisions.get(name):
            continue
        n_grants += 1
        role = rows.get(name, {}).get("role", "official").replace("_", " ")
        clients = _client_pool(fam, dynasties[fam], personas, rows, _FAVORS)
        for client in clients:
            story = random.choice(_FAVOR_STORIES)
            text = (f"{name} (barangay {role}, {fam} family) {story} — "
                    f"they remember us when it matters.")
            if _add_memory(personas[client], text, curr_time, poignancy=_poig(7),
                           s=name, p="helped", o=client,
                           kw={"service", "loyalty", "utang", name, fam}):
                n_favors += 1
        # A few connected observers read the same act as machine politics.
        watchers = random.sample(list(personas), min(6, len(personas)))
        w_text = (f"{name} ({fam} family) keeps handing out favors around the "
                  f"barangay — the family is buying loyalty ahead of anything "
                  f"that threatens their hold.")
        for w in watchers:
            if w == name or w in clients:
                continue
            _add_memory(personas[w], w_text, curr_time, poignancy=4,
                        s=name, p="cultivates", o="clients",
                        kw={"corruption", name, fam}, expire_days=30)

    if officials:
        print(f"[PATRONAGE] {n_grants}/{len(officials)} dynasty officials "
              f"renewed the machine ({n_favors} favors granted)", flush=True)
    return n_grants, n_favors
