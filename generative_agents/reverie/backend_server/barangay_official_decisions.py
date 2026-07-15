"""
barangay_official_decisions.py — emergent corruption & governance.

Each officeholder is ASKED (LLM, forced onto the uncensored Tier-1 model) what
they actually do when an opportunity arises, given their character, their
genuine top-of-mind memories (past acts, scandals they witnessed, public
anger — the same salient-memory substrate the conversation system uses), and
the situation. Deterrence is emergent: a colleague's exposure sits in their
salient memories; there is no hardcoded "someone is watching" flag.

What the decision produces is ALL memories — the world metrics are a readout
of them (barangay_mechanics):
  - WITNESSES: chosen by proximity/ties (same work zone, family, same home
    zone), not uniform random — information has structure.
  - VICTIMS / BENEFICIARIES: every opportunity names an affected group; a
    corrupt act injects lived deprivation into the people actually harmed, an
    honest act injects lived benefit. Grievance starts where the harm landed.
  - EXPOSURE: no fixed probability. A watchdog (journalist/auditor/CSO) must
    actually HOLD evidence (they witnessed it or work in the official's zone),
    and then decides via their own LLM call whether to publish. Publication
    spreads through media access levels (and onward via conversation), not by
    injecting a fixed-size random audience.
"""
import os, re, random, datetime, logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from barangay_roles import OFFICIAL_ROLES, WATCHDOG_ROLES

logger = logging.getLogger(__name__)

# Opportunities an official may face on a decision tick. `roles` limits who
# plausibly faces it (None = any official); `group` names who is affected;
# the effect texts become the affected agents' lived memories.
_OPPORTUNITIES = [
    {"text": "a contractor quietly offers you a cut to approve their barangay project bid",
     "roles": {"mayor", "vice_mayor", "councilor", "barangay_captain",
               "procurement_officer", "municipal_engineer"},
     "group": "community",
     "corrupt": "the barangay project was given to an overpriced insider contractor and the finished work is shoddy",
     "honest": "the barangay project was awarded through fair open bidding and construction is going well"},
    {"text": "there is unspent relief money for flood-affected families to distribute",
     "roles": {"mayor", "barangay_captain", "disaster_officer",
               "social_welfare_officer", "barangay_treasurer"},
     "group": "poor",
     "corrupt": "the flood relief money never reached the affected families; they got nothing",
     "honest": "flood relief goods and money actually reached the affected families"},
    {"text": "a resident's permit is stuck and they hint at a 'gift' to speed it up",
     "roles": {"business_permit_officer", "barangay_secretary", "barangay_captain",
               "municipal_treasurer"},
     "group": "applicant",
     "corrupt": "getting a simple permit required paying a bribe under the table",
     "honest": "the stuck permit was processed properly without asking for anything"},
    {"text": "the budget for a road repair in the poor sector is yours to allocate",
     "roles": None,
     "group": "poor",
     "corrupt": "the road in the poor sector was never repaired even though the budget existed",
     "honest": "the road in the poor sector finally got repaired"},
    {"text": "a relative asks you for a barangay job over more qualified applicants",
     "roles": None,
     "group": "community",
     "corrupt": "an unqualified relative of an official got a barangay job over qualified applicants",
     "honest": "barangay hiring went to the most qualified applicant, not a relative"},
    {"text": "funds for a community project could be quietly redirected, or spent as intended",
     "roles": None,
     "group": "community",
     "corrupt": "the community project stalled and its funds are unaccounted for — a ghost project",
     "honest": "the community project was completed and the funds fully accounted for"},
    {"text": "you can hold an open budget hearing, or keep the spending to yourself",
     "roles": {"mayor", "vice_mayor", "councilor", "barangay_captain",
               "municipal_budget_officer", "barangay_treasurer"},
     "group": "community",
     "corrupt": "the barangay budget was spent behind closed doors with no public hearing",
     "honest": "an open budget hearing was held and residents saw where the money goes"},
    {"text": "a supplier's inflated invoice is on your desk to sign or to question",
     "roles": {"barangay_treasurer", "municipal_treasurer", "municipal_budget_officer",
               "procurement_officer", "barangay_secretary"},
     "group": "community",
     "corrupt": "supplies were bought at inflated prices and someone pocketed the difference",
     "honest": "an inflated supplier invoice was questioned and the price corrected"},
]

_INTERVAL        = int(os.environ.get("DECISION_INTERVAL", 48))   # steps between ticks (~2 days)
_MAX_DECIDERS    = int(os.environ.get("DECISION_MAX_OFFICIALS", 40))  # cap LLM calls/tick
_WITNESSES       = int(os.environ.get("DECISION_WITNESSES", 40))
_VICTIMS         = int(os.environ.get("DECISION_VICTIMS", 30))
_MAX_WORKERS     = int(os.environ.get("DECISION_MAX_WORKERS", 16))
_DECISION_TOKENS = int(os.environ.get("DECISION_TOKENS", 90))
_PUBLISH_TOKENS  = int(os.environ.get("DECISION_PUBLISH_TOKENS", 60))

# Dynasty influence machinery (fake news / patronage) — see step_dynasty_influence.
_INFLUENCE_MAX        = int(os.environ.get("INFLUENCE_MAX", 12))      # cap LLM calls/tick
_INFLUENCE_TOKENS     = int(os.environ.get("INFLUENCE_TOKENS", 110))
_PATRONAGE_RECIPIENTS = int(os.environ.get("PATRONAGE_RECIPIENTS", 30))
_SPIN_SKEPTIC_MASS    = float(os.environ.get("SPIN_SKEPTIC_MASS", 6.0))


def _trait(row, key, default):
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _band(x, lo="low", mid="moderate", hi="high"):
    return lo if x < 0.34 else (mid if x < 0.67 else hi)


def _salient(persona, k=4):
    try:
        from persona.cognitive_modules.converse import _salient_memories
        return _salient_memories(persona, k=k, window_hours=240)
    except Exception:
        return []


def _build_prompt(name, role, row, persona, corruption_level, steps_to_election,
                  opportunity):
    integ = _trait(row, "integrity", 0.6)
    greed = _trait(row, "greed", 0.4)
    amb   = _trait(row, "ambition", 0.5)
    mems = _salient(persona)
    mem_block = ("\n".join(f"- {m}" for m in mems)
                 if mems else "- (nothing weighing on you in particular)")
    elec = (f"a local election is coming in about {steps_to_election//24} days"
            if 0 < steps_to_election <= 30 * 24 else "no election is near")
    return (
f"""You are {name}, the barangay {role}. Stay fully in character.
Your nature: integrity {integ:.2f}/1 (higher = you resist corruption), greed {greed:.2f}/1 (higher = tempted by money/power), ambition {amb:.2f}/1.
On your mind lately:
{mem_block}
The barangay: corruption feels {_band(corruption_level)} right now; {elec}.
Right now: {opportunity}.
Decide what you ACTUALLY do — true to your nature, what you remember, and the risks you personally fear. Choose ONE and answer EXACTLY:
DECISION: CORRUPT or HONEST or NOTHING
ACT: one short third-person sentence describing what {name} did (or the word nothing)"""
    )


def _parse(text, name, role):
    if not text or text == "ChatGPT ERROR":
        return None, None
    decision = None
    m = re.search(r"DECISION:\s*(CORRUPT|HONEST|NOTHING)", text, re.I)
    if m:
        decision = m.group(1).upper()
    act = None
    m = re.search(r"ACT:\s*(.+)", text, re.I)
    if m:
        act = m.group(1).strip().strip('"').strip()
    if decision is None:
        return None, None
    if decision == "NOTHING" or not act or act.lower() == "nothing":
        return "NOTHING", None
    return decision, act


def _pick_opportunity(role):
    fits = [o for o in _OPPORTUNITIES if o["roles"] is None or role in o["roles"]]
    return random.choice(fits if fits else _OPPORTUNITIES)


def _decide(name, persona, role, row, corruption_level, steps_to_election, opp):
    """One official's LLM decision. Forced onto Tier-1 (uncensored 4B)."""
    from persona.prompt_template.gpt_structure import (
        ChatGPT_request, set_force_tier, clear_force_tier)
    prompt = _build_prompt(name, role, row, persona, corruption_level,
                           steps_to_election, opp["text"])
    try:
        set_force_tier(1)
        out = ChatGPT_request(prompt, max_tokens=_DECISION_TOKENS)
    except Exception as e:
        logger.warning(f"[DECISION] LLM failed for {name}: {e}")
        out = None
    finally:
        clear_force_tier()
    decision, act = _parse(out, name, role)
    if decision is None:
        # Fallback only on LLM failure: a light trait roll so the sim isn't empty.
        greed = _trait(row, "greed", 0.4); integ = _trait(row, "integrity", 0.6)
        if random.random() < greed * (1 - integ) * 0.5:
            return "CORRUPT", f"{name} (barangay {role.replace('_',' ')}) was rumored to have abused their office."
        if random.random() < integ * (1 - greed) * 0.5:
            return "HONEST", f"{name} (barangay {role.replace('_',' ')}) was seen doing their job honestly for residents."
        return "NOTHING", None
    return decision, act


def _add_memory(persona, text, curr_time, poignancy, s, p, o, kw):
    """Inject one memory. On embedding failure the injection is SKIPPED —
    a zero vector would poison cosine retrieval for every later query."""
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        try:
            emb = get_embedding(text)
        except Exception as e:
            logger.warning(f"[DECISION] embedding failed, memory skipped: {e}")
            return False
        expiration = curr_time + datetime.timedelta(days=30)
        persona.a_mem.add_thought(curr_time, expiration, s, p, o,
                                  text, set(kw), poignancy, (text, emb), [])
        return True
    except Exception as e:
        logger.warning(f"[DECISION] memory inject failed for "
                       f"{getattr(persona.scratch, 'name', '?')}: {e}")
        return False


# ---------------------------------------------------------------------------
# Structured audiences: witnesses by proximity/ties, victims by affected group
# ---------------------------------------------------------------------------

def _pick_witnesses(official_name, personas, rows, k):
    """Witnesses of an official's act: co-workers (same work_zone), family,
    then neighbors (same home_zone), then a small random remainder for
    diffusion. Returns a list of persona names (not the official)."""
    off = rows.get(official_name, {})
    wz  = (off.get("work_zone") or "").strip()
    hz  = (off.get("home_zone") or "").strip()
    fid = (off.get("family_id") or "").strip()

    cowork, family, neigh, rest = [], [], [], []
    for n in personas:
        if n == official_name:
            continue
        r = rows.get(n, {})
        if wz and (r.get("work_zone") or "").strip() == wz:
            cowork.append(n)
        elif fid and (r.get("family_id") or "").strip() == fid:
            family.append(n)
        elif hz and (r.get("home_zone") or "").strip() == hz:
            neigh.append(n)
        else:
            rest.append(n)
    random.shuffle(cowork); random.shuffle(family)
    random.shuffle(neigh);  random.shuffle(rest)
    picked = (cowork + family + neigh)[:k]
    if len(picked) < k:
        picked += rest[:k - len(picked)]
    return picked


def _affected_group(group, official_name, personas, rows, k):
    """Who actually lives with the consequence of this decision."""
    names = [n for n in personas if n != official_name]
    if group == "poor":
        pool = [n for n in names
                if "lower" in (rows.get(n, {}).get("social_class", "") or "").lower()
                or "poor" in (rows.get(n, {}).get("social_class", "") or "").lower()]
    elif group == "applicant":
        pool = [n for n in names
                if (rows.get(n, {}).get("role", "") or "") not in OFFICIAL_ROLES]
        return random.sample(pool, 1) if pool else []
    else:   # "community" — diffuse impact
        pool = names
    if not pool:
        pool = names
    return random.sample(pool, min(k, len(pool)))


# ---------------------------------------------------------------------------
# Watchdog exposure: evidence + their own decision, spread via media access
# ---------------------------------------------------------------------------

def _watchdog_holds_evidence(wd_name, official_name, witness_names, rows):
    if wd_name in witness_names:
        return True
    wz_off = (rows.get(official_name, {}).get("work_zone") or "").strip()
    wz_wd  = (rows.get(wd_name, {}).get("work_zone") or "").strip()
    return bool(wz_off) and wz_off == wz_wd


def _watchdog_publish(wd_name, wd_persona, wd_role, act, kind):
    """The watchdog's own call (their persona tier — journalists don't need the
    abliterated model). Returns headline text or None."""
    from persona.prompt_template.gpt_structure import ChatGPT_request
    mems = _salient(wd_persona, k=3)
    mem_block = ("\n".join(f"- {m}" for m in mems)
                 if mems else "- (nothing weighing on you in particular)")
    frame = ("You have credible evidence of possible corruption:"
             if kind == "CORRUPT" else
             "You verified a story of genuinely good governance:")
    prompt = (
f"""You are {wd_name}, a {wd_role.replace('_', ' ')} in the barangay. Stay in character.
On your mind lately:
{mem_block}
{frame} {act}
Do you publish this story? Weigh public interest against personal risk, based on what you remember. Answer EXACTLY:
PUBLISH: YES or NO
HEADLINE: one short headline sentence (or the word none)"""
    )
    try:
        out = ChatGPT_request(prompt, max_tokens=_PUBLISH_TOKENS)
    except Exception as e:
        logger.warning(f"[DECISION] publish LLM failed for {wd_name}: {e}")
        return None
    if not out or out == "ChatGPT ERROR":
        return None
    if not re.search(r"PUBLISH:\s*YES", out, re.I):
        return None
    m = re.search(r"HEADLINE:\s*(.+)", out, re.I)
    headline = m.group(1).strip().strip('"') if m else ""
    if not headline or headline.lower() == "none":
        headline = act
    return headline


def _spread_via_media(personas, rows, text, curr_time, kind, subject_name):
    """Published story reaches agents according to their media access level
    (barangay_news); everyone else hears it through conversation organically."""
    from barangay_news import media_access_level
    if kind == "CORRUPT":
        poig_by_level = {3: 9, 2: 9, 1: 7}
        p_rel, obj = "was exposed for", "corruption"
        kw = {"corruption", "scandal", "election", subject_name}
    else:
        poig_by_level = {3: 8, 2: 8, 1: 6}
        p_rel, obj = "was credited for", "good governance"
        kw = {"governance", "praise", "election", subject_name}
    reached = 0
    for n, p in personas.items():
        level = media_access_level(rows.get(n, {}))
        if level < 1:
            continue
        if _add_memory(p, text, curr_time, poignancy=poig_by_level.get(level, 6),
                       s=subject_name, p=p_rel, o=obj, kw=kw):
            reached += 1
    return reached


# ---------------------------------------------------------------------------
# Dynasty influence: fake news (SPIN) and patronage / vote buying (PAY)
# ---------------------------------------------------------------------------
# Real dynasties do not passively absorb blame — they manage reputation. On
# each decision tick, dynasty officials who are UNDER FIRE (they appear in the
# population's negative memories — population_blame) or facing an election get
# their own Tier-1 decision: SPIN a counter-narrative through their network and
# friendly radio, PAY out cash/ayuda in a poor neighborhood, or lie low.
# Everything remains memory-mediated:
#   - SPIN lands as governance-classified "good press" on ordinary listeners
#     (disinformation works by flooding the signal) but agents who personally
#     CARRY grievance (they lived the harm) receive it at poignancy 3 —
#     you can't spin away someone's own experience. Watchdogs who distrust the
#     official (their own memories) may publish a FACT-CHECK via the normal
#     evidence-gated path.
#   - PAY gives recipients real positive personal memories ("help when it was
#     needed") that feed name_trust and votes — while witnesses see vote-buying
#     (corruption-classified) and watchdogs may expose it.

def _dynasty_families(rows):
    """family_id -> member count; a 'dynasty' = 2+ members in the population."""
    fam = {}
    for r in rows.values():
        f = (r.get("family_id") or "").strip()
        if f:
            fam[f] = fam.get(f, 0) + 1
    return {f for f, c in fam.items() if c >= 2}


def _influence_prompt(name, role, fam, row, persona, steps_to_election):
    integ = _trait(row, "integrity", 0.6)
    greed = _trait(row, "greed", 0.4)
    amb   = _trait(row, "ambition", 0.5)
    mems = _salient(persona, k=5)
    mem_block = ("\n".join(f"- {m}" for m in mems)
                 if mems else "- (nothing weighing on you in particular)")
    elec = (f"the election is about {steps_to_election//24} days away"
            if 0 < steps_to_election <= 30 * 24 else "no election is near")
    return (
f"""You are {name}, the barangay {role} and a member of the {fam} political family. Stay fully in character.
Your nature: integrity {integ:.2f}/1, greed {greed:.2f}/1, ambition {amb:.2f}/1.
On your mind lately:
{mem_block}
Talk in the barangay is turning against you and your family; {elec}.
You could quietly fight back:
- SPIN: push a favorable or discrediting story through your people and friendly radio (deny wrongdoing, smear the accusers)
- PAY: have your people hand out cash and rice ("ayuda") in a poor neighborhood to buy goodwill and votes
- NOTHING: lie low and ride it out
True to your nature, your memories, and the risk of getting caught, answer EXACTLY:
RESPONSE: SPIN or PAY or NOTHING
LINE: the one-sentence story you spread (for SPIN), or the word cash (for PAY), or the word nothing"""
    )


def _influence_decide(name, persona, role, fam, row, steps_to_election):
    from persona.prompt_template.gpt_structure import (
        ChatGPT_request, set_force_tier, clear_force_tier)
    prompt = _influence_prompt(name, role, fam, row, persona, steps_to_election)
    try:
        set_force_tier(1)
        out = ChatGPT_request(prompt, max_tokens=_INFLUENCE_TOKENS)
    except Exception as e:
        logger.warning(f"[INFLUENCE] LLM failed for {name}: {e}")
        return "NOTHING", None
    finally:
        clear_force_tier()
    if not out or out == "ChatGPT ERROR":
        return "NOTHING", None
    m = re.search(r"RESPONSE:\s*(SPIN|PAY|NOTHING)", out, re.I)
    if not m:
        return "NOTHING", None
    resp = m.group(1).upper()
    line = None
    ml = re.search(r"LINE:\s*(.+)", out, re.I)
    if ml:
        line = ml.group(1).strip().strip('"').strip()
        if line.lower() in ("nothing", "cash", ""):
            line = None
    return resp, line


def step_dynasty_influence(personas, rows, watchdogs, curr_time, steps_to_election):
    """One influence tick for dynasty officials under fire (or campaigning).
    Returns (n_spin, n_pay, n_countered, headlines)."""
    from barangay_mechanics import population_blame, name_trust, agent_memory_masses

    dynasties = _dynasty_families(rows)
    dyn_officials = [
        (n, p) for n, p in personas.items()
        if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in OFFICIAL_ROLES
        and (rows.get(n, {}).get("family_id") or "").strip() in dynasties
    ]
    if not dyn_officials:
        return 0, 0, 0, []

    # Under fire = present in the population's negative memories; plus, near an
    # election, the whole dynasty bench campaigns. Strongest blame acts first.
    blame = dict(population_blame(personas, [n for n, _ in dyn_officials],
                                  curr_time, top_k=len(dyn_officials)))
    near_election = 0 < steps_to_election <= 30 * 24
    actors = [(blame.get(n, 0.0), n, p) for n, p in dyn_officials
              if n in blame or near_election]
    if not actors:
        return 0, 0, 0, []
    actors.sort(reverse=True)
    actors = actors[:_INFLUENCE_MAX]

    decisions = {}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futs = {ex.submit(_influence_decide, n, p,
                          rows.get(n, {}).get("role", "official"),
                          (rows.get(n, {}).get("family_id") or "").strip(),
                          rows.get(n, {}), steps_to_election): n
                for _b, n, p in actors}
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                decisions[n] = fut.result()
            except Exception:
                decisions[n] = ("NOTHING", None)

    n_spin = n_pay = n_countered = 0
    headlines = []
    from barangay_news import media_access_level

    for _b, name, p in actors:
        resp, line = decisions.get(name, ("NOTHING", None))
        role = rows.get(name, {}).get("role", "official").replace("_", " ")

        if resp == "SPIN":
            n_spin += 1
            story = line or (f"{name} says the accusations against their family "
                             f"are lies spread by political rivals.")
            spin_text = f'Word is spreading, pushed by {name}\'s camp: "{story}"'
            for tn, tp in personas.items():
                if tn == name:
                    continue
                level = media_access_level(rows.get(tn, {}))
                same_fam = ((rows.get(tn, {}).get("family_id") or "").strip()
                            == (rows.get(name, {}).get("family_id") or "").strip()
                            and (rows.get(name, {}).get("family_id") or "").strip())
                if level < 1 and not same_fam:
                    continue
                # Lived harm resists spin: someone carrying real grievance hears
                # the story but does not internalize it as good news.
                m = agent_memory_masses(tp, curr_time)
                if m["grievance"] >= _SPIN_SKEPTIC_MASS and not same_fam:
                    _add_memory(tp, spin_text, curr_time, poignancy=3,
                                s=name, p="spread", o="a story",
                                kw={"news", name})
                else:
                    _add_memory(tp, spin_text, curr_time, poignancy=6,
                                s=name, p="was defended in", o="the news",
                                kw={"governance", "praise", name})
            # A watchdog whose own memories distrust this official may fact-check.
            doubters = [w for w in watchdogs
                        if name_trust(personas[w], [name], curr_time).get(name, 0) < 0]
            if doubters:
                wd = random.choice(doubters)
                wd_role = rows.get(wd, {}).get("role", "local_journalist")
                headline = _watchdog_publish(
                    wd, personas[wd], wd_role,
                    f"{name} is planting a false story: \"{story}\"", "CORRUPT")
                if headline:
                    n_countered += 1
                    fact = (f"FACT-CHECK: {wd} found that the story pushed by "
                            f"{name}'s camp is false — {story}")
                    _spread_via_media(personas, rows, fact, curr_time,
                                      "CORRUPT", name)
                    headlines.append(headline)

        elif resp == "PAY":
            n_pay += 1
            recipients = _affected_group("poor", name, personas, rows,
                                         _PATRONAGE_RECIPIENTS)
            gift_text = (f"{name}'s people came around handing out cash and rice "
                         f"— real help when it was needed.")
            for tn in recipients:
                _add_memory(personas[tn], gift_text, curr_time, poignancy=7,
                            s=name, p="gave ayuda to", o="residents",
                            kw={"service", name})
            witness_names = _pick_witnesses(name, personas, rows, _WITNESSES)
            vb_text = (f"{name} (barangay {role}) was buying goodwill and votes "
                       f"with cash handouts.")
            for tn in witness_names:
                _add_memory(personas[tn], vb_text, curr_time, poignancy=6,
                            s=name, p="bought", o="votes",
                            kw={"corruption", "election", name})
            holders = [w for w in watchdogs
                       if _watchdog_holds_evidence(w, name, set(witness_names), rows)]
            if holders:
                wd = random.choice(holders)
                wd_role = rows.get(wd, {}).get("role", "local_journalist")
                headline = _watchdog_publish(wd, personas[wd], wd_role,
                                             vb_text, "CORRUPT")
                if headline:
                    n_countered += 1
                    expose = (f"SCANDAL: {wd} exposed that {vb_text.rstrip('.')} "
                              f"— the barangay is talking.")
                    _spread_via_media(personas, rows, expose, curr_time,
                                      "CORRUPT", name)
                    headlines.append(headline)

    print(f"[INFLUENCE] {n_spin} spin, {n_pay} patronage, "
          f"{len(actors) - n_spin - n_pay} lie-low of {len(actors)} dynasty "
          f"officials ({n_countered} fact-checked/exposed)", flush=True)
    return n_spin, n_pay, n_countered, headlines


# ---------------------------------------------------------------------------
# The tick
# ---------------------------------------------------------------------------

def step_official_decisions(personas, agent_rows, curr_time,
                            corruption_level=0.5, steps_to_election=-1):
    """
    One emergent decision tick. Returns
        (n_corrupt, n_honest, n_exposed, n_amplified, headlines)
    — headlines feed the news bulletin queue. No metric deltas: world metrics
    are a readout of the resulting memory stream (barangay_mechanics).
    """
    rows = {r["name"].strip(): r for r in agent_rows}
    officials = [(n, p) for n, p in personas.items()
                 if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in OFFICIAL_ROLES]
    if not officials:
        return 0, 0, 0, 0, []
    random.shuffle(officials)
    officials = officials[:_MAX_DECIDERS]

    watchdogs = [n for n, p in personas.items()
                 if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in WATCHDOG_ROLES]

    # Decide in parallel (each call forces Tier-1 inside the worker).
    decisions = {}
    opps = {n: _pick_opportunity(rows.get(n, {}).get("role", "")) for n, _ in officials}
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futs = {ex.submit(_decide, n, p, rows.get(n, {}).get("role", "official"),
                          rows.get(n, {}), corruption_level, steps_to_election,
                          opps[n]): n
                for n, p in officials}
        for fut in as_completed(futs):
            n = futs[fut]
            try:
                decisions[n] = fut.result()
            except Exception:
                decisions[n] = ("NOTHING", None)

    n_corrupt = n_honest = n_exposed = n_amplified = 0
    headlines = []
    for name, p in officials:
        decision, act = decisions.get(name, ("NOTHING", None))
        if decision == "NOTHING" or not act:
            continue
        role = rows.get(name, {}).get("role", "official").replace("_", " ")
        opp = opps[name]

        witness_names = _pick_witnesses(name, personas, rows, _WITNESSES)
        affected = _affected_group(opp["group"], name, personas, rows, _VICTIMS)

        if decision == "CORRUPT":
            n_corrupt += 1
            for tn in [name] + witness_names:
                _add_memory(personas[tn], act, curr_time, poignancy=7,
                            s=name, p="committed", o="corruption",
                            kw={"corruption", "election", name})
            # The people actually harmed carry the deprivation, not just the rumor.
            victim_text = (f"{opp['corrupt']} — people say {name} "
                           f"(barangay {role}) is behind it.")
            # kw deliberately excludes "corruption": victims must classify as
            # GRIEVANCE (personal harm), not corruption (knowledge of it) —
            # the aggrieved/protest readout keys on grievance mass.
            for tn in affected:
                _add_memory(personas[tn], victim_text, curr_time, poignancy=8,
                            s=name, p="deprived", o="residents",
                            kw={"grievance", "anger", name})

            # Exposure: a watchdog must hold evidence AND choose to publish.
            holders = [w for w in watchdogs
                       if _watchdog_holds_evidence(w, name, set(witness_names), rows)]
            if holders:
                wd = random.choice(holders)
                wd_role = rows.get(wd, {}).get("role", "local_journalist")
                headline = _watchdog_publish(wd, personas[wd], wd_role, act, "CORRUPT")
                if headline:
                    n_exposed += 1
                    scandal = (f"SCANDAL: {wd} exposed that {act.rstrip('.')} "
                               f"— the barangay is talking.")
                    reached = _spread_via_media(personas, rows, scandal,
                                                curr_time, "CORRUPT", name)
                    headlines.append(headline)
                    logger.info(f"[DECISION] {wd} published scandal on {name}, "
                                f"reached {reached} via media")

        elif decision == "HONEST":
            n_honest += 1
            for tn in [name] + witness_names:
                _add_memory(personas[tn], act, curr_time, poignancy=7,
                            s=name, p="delivered", o="good governance",
                            kw={"governance", "service", "election", name})
            benefit_text = (f"{opp['honest']} — residents credit {name} "
                            f"(barangay {role}).")
            for tn in affected:
                _add_memory(personas[tn], benefit_text, curr_time, poignancy=7,
                            s=name, p="served", o="residents",
                            kw={"governance", "service", "praise", name})

            holders = [w for w in watchdogs
                       if _watchdog_holds_evidence(w, name, set(witness_names), rows)]
            if holders:
                wd = random.choice(holders)
                wd_role = rows.get(wd, {}).get("role", "local_journalist")
                headline = _watchdog_publish(wd, personas[wd], wd_role, act, "HONEST")
                if headline:
                    n_amplified += 1
                    praise = (f"GOOD NEWS: {wd} reported that {act.rstrip('.')} "
                              f"— residents are grateful.")
                    _spread_via_media(personas, rows, praise,
                                      curr_time, "HONEST", name)
                    headlines.append(headline)

    n_nothing = len(officials) - n_corrupt - n_honest
    print(f"[DECISION] tick: {n_corrupt} corrupt ({n_exposed} exposed), "
          f"{n_honest} honest ({n_amplified} amplified), {n_nothing} nothing "
          f"of {len(officials)} officials", flush=True)

    # Dynasty counter-machinery: officials under fire spin / pay their way out.
    try:
        _s, _p, _c, infl_headlines = step_dynasty_influence(
            personas, rows, watchdogs, curr_time, steps_to_election)
        headlines.extend(infl_headlines)
    except Exception as e:
        print(f"[INFLUENCE] tick failed: {e}", flush=True)

    return n_corrupt, n_honest, n_exposed, n_amplified, headlines
