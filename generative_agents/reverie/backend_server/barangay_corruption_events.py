"""
barangay_corruption_events.py — active corruption that the population witnesses.

Periodically, officials with high greed / low integrity may commit a corrupt act
(bribe, embezzlement, kickback, nepotism). Each act:
  - is injected as an associative memory into a sample of agents (so it surfaces
    in the memory-based election voting — agents who heard vote against them),
  - raises the world corruption index (which the weekly news bulletin reflects),
  - may be EXPOSED by a journalist / COA auditor → a louder "scandal" broadcast
    to many more agents at higher poignancy (bigger reputation hit).

This turns the corruption index from a passive trait-average into behaviour with
consequences: corruption → public awareness → trust erosion → votes. Templated
text (no LLM generation); only embeddings per injected memory.
"""
import os, random, datetime, logging

logger = logging.getLogger(__name__)

OFFICIAL_ROLES = {
    "mayor", "vice_mayor", "councilor",
    "barangay_captain", "barangay_kagawad", "barangay_treasurer", "barangay_secretary",
    "municipal_engineer", "municipal_budget_officer", "municipal_treasurer",
    "procurement_officer", "business_permit_officer", "disaster_officer",
    "social_welfare_officer",
}
WATCHDOG_ROLES = {"local_journalist", "coa_auditor", "cso_organizer"}

_ACTS = {
    "bribe":     "{who} accepted a bribe to fast-track a permit application.",
    "embezzle":  "{who} is said to have diverted barangay funds for personal use.",
    "kickback":  "{who} took a kickback from a contractor on a barangay project.",
    "nepotism":  "{who} handed a barangay position to a relative over better-qualified applicants.",
    "ghost":     "{who} was linked to a 'ghost project' that was paid for but never built.",
}

# Tunables (env-overridable)
_INTERVAL      = int(os.environ.get("CORRUPTION_INTERVAL", 48))   # steps between checks (~2 days)
_BASE_CHANCE   = float(os.environ.get("CORRUPTION_CHANCE", 0.20)) # scales greed*(1-integrity)
_MAX_PER_TICK  = int(os.environ.get("CORRUPTION_MAX", 2))
_WITNESSES     = int(os.environ.get("CORRUPTION_WITNESSES", 40))  # agents who "hear" a quiet act
_EXPOSE_AUDIENCE = int(os.environ.get("CORRUPTION_EXPOSE_AUDIENCE", 200))


def _add_memory(persona, text, curr_time, poignancy, s, p, o, kw):
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        expiration = curr_time + datetime.timedelta(days=30)
        try:
            emb = get_embedding(text)
        except Exception:
            emb = [0.0] * 768
        persona.a_mem.add_thought(curr_time, expiration, s, p, o,
                                  text, set(kw), poignancy, (text, emb), [])
    except Exception as e:
        logger.warning(f"[CORRUPTION] memory inject failed for {persona.scratch.name}: {e}")


def step_corruption_events(personas, agent_rows, curr_time):
    """
    Run one corruption tick. Returns (n_events, n_exposed, corruption_delta) so
    reverie can nudge the world corruption index. Call every _INTERVAL steps.
    """
    rows = {r["name"].strip(): r for r in agent_rows}
    officials = [(n, p) for n, p in personas.items()
                 if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in OFFICIAL_ROLES]
    if not officials:
        return 0, 0, 0.0
    random.shuffle(officials)

    watchdogs = [n for n, p in personas.items()
                 if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in WATCHDOG_ROLES]
    all_personas = list(personas.values())
    events = exposed = 0
    delta = 0.0

    for name, p in officials:
        if events >= _MAX_PER_TICK:
            break
        r = rows.get(name, {})
        greed = float(r.get("greed", 0.3)); integ = float(r.get("integrity", 0.7))
        propensity = greed * (1.0 - integ)            # 0..1
        if random.random() >= propensity * _BASE_CHANCE:
            continue

        act = random.choice(list(_ACTS))
        role = r.get("role", "official").replace("_", " ")
        who = f"{name} (barangay {role})"
        text = _ACTS[act].format(who=who)
        events += 1
        delta += 0.015

        # The official + a quiet sample of agents become aware (rumor spread).
        sample = random.sample(all_personas, min(_WITNESSES, len(all_personas)))
        for tp in [personas[name]] + sample:
            _add_memory(tp, text, curr_time, poignancy=7,
                        s=name, p="committed", o="corruption",
                        kw={"corruption", "election", name})

        # Exposure: a watchdog may catch it -> public scandal (louder, wider).
        if watchdogs and random.random() < 0.35:
            exposed += 1
            wd = random.choice(watchdogs)
            scandal = (f"SCANDAL: {wd} exposed that {text[:-1]} — the barangay is talking.")
            wide = random.sample(all_personas, min(_EXPOSE_AUDIENCE, len(all_personas)))
            for tp in wide:
                _add_memory(tp, scandal, curr_time, poignancy=9,
                            s=name, p="was exposed for", o="corruption",
                            kw={"corruption", "scandal", "election", name})
            delta += 0.02

    if events:
        print(f"[CORRUPTION] {events} act(s), {exposed} exposed; corruption +{delta:.3f}",
              flush=True)
    return events, exposed, delta
