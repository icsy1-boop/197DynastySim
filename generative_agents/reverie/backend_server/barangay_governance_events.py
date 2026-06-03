"""
barangay_governance_events.py — good governance as the mirror of corruption.

The symmetric counterpart to barangay_corruption_events: where greedy / low-
integrity officials commit corrupt acts that raise corruption and erode trust,
WELL-MEANING officials (high integrity, low greed) take pro-social actions that:
  - lower the world corruption index (reform/transparency), and/or
  - raise welfare directly (delivered services, honest relief, finished projects),
  - are injected as POSITIVE memories into a sample of agents, so residents who
    heard credit them — and vote FOR them in the memory-based election.
  - may be AMPLIFIED by a journalist / CSO organizer → a wider, higher-poignancy
    "good news" broadcast (a reputation boost), mirroring scandal exposure.

This gives the simulation a recovery path: electing cleaner officials → good
governance → corruption down, welfare up, unrest down (through the existing
welfare/unrest drift in barangay_mechanics) → re-election. Templated text (no
LLM generation); one embedding per injected memory.

Tunables mirror the corruption module so the two pathways stay comparable.
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

# Each act: (template, welfare_gain, corruption_cut). Service/relief mainly lift
# welfare; reform/transparency mainly cut corruption.
_ACTS = {
    "service":      ("{who} made sure the {thing} reached residents on time.",            0.020, 0.005),
    "project":      ("{who} completed the stalled {thing}, and it was built properly.",   0.018, 0.006),
    "relief":       ("{who} distributed relief aid fairly so the neediest families got it.", 0.022, 0.005),
    "reform":       ("{who} pushed through an anti-corruption rule requiring open bidding and audits.", 0.006, 0.022),
    "transparency": ("{who} held an open budget hearing and published the barangay's spending.", 0.006, 0.018),
}
_THINGS = ["road repair in Residential C", "drainage clean-up", "health center supplies",
           "barangay scholarship payout", "water line repair", "garbage collection schedule",
           "feeding program", "street lighting fix"]

# Tunables (env-overridable) — mirror barangay_corruption_events.
_INTERVAL        = int(os.environ.get("GOVERNANCE_INTERVAL", 48))    # steps between checks
_BASE_CHANCE     = float(os.environ.get("GOVERNANCE_CHANCE", 0.20))  # scales integrity*(1-greed)
_MAX_PER_TICK    = int(os.environ.get("GOVERNANCE_MAX", 2))
_WITNESSES       = int(os.environ.get("GOVERNANCE_WITNESSES", 40))   # agents who hear of a quiet good act
_PRAISE_AUDIENCE = int(os.environ.get("GOVERNANCE_PRAISE_AUDIENCE", 200))


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
        logger.warning(f"[GOVERNANCE] memory inject failed for {persona.scratch.name}: {e}")


def step_governance_events(personas, agent_rows, curr_time):
    """
    Run one good-governance tick. Returns (n_events, n_amplified, welfare_delta,
    corruption_delta) so reverie can lift welfare and cut corruption. corruption_delta
    is NEGATIVE (reform reduces corruption). Call every _INTERVAL steps.
    """
    rows = {r["name"].strip(): r for r in agent_rows}
    officials = [(n, p) for n, p in personas.items()
                 if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in OFFICIAL_ROLES]
    if not officials:
        return 0, 0, 0.0, 0.0
    random.shuffle(officials)

    watchdogs = [n for n, p in personas.items()
                 if getattr(p.scratch, "role", rows.get(n, {}).get("role", "")) in WATCHDOG_ROLES]
    all_personas = list(personas.values())
    events = amplified = 0
    welfare_delta = 0.0
    corruption_delta = 0.0

    for name, p in officials:
        if events >= _MAX_PER_TICK:
            break
        r = rows.get(name, {})
        greed = float(r.get("greed", 0.3)); integ = float(r.get("integrity", 0.7))
        propensity = integ * (1.0 - greed)            # 0..1 — the inverse of corruption
        if random.random() >= propensity * _BASE_CHANCE:
            continue

        act = random.choice(list(_ACTS))
        tmpl, w_gain, c_cut = _ACTS[act]
        role = r.get("role", "official").replace("_", " ")
        who = f"{name} (barangay {role})"
        text = tmpl.format(who=who, thing=random.choice(_THINGS))
        events += 1
        welfare_delta += w_gain
        corruption_delta -= c_cut

        # The official + a quiet sample of residents notice the good work.
        sample = random.sample(all_personas, min(_WITNESSES, len(all_personas)))
        for tp in [personas[name]] + sample:
            _add_memory(tp, text, curr_time, poignancy=7,
                        s=name, p="delivered", o="good governance",
                        kw={"governance", "service", "election", name})

        # Amplification: a watchdog may publicly credit it -> wider praise.
        if watchdogs and random.random() < 0.35:
            amplified += 1
            wd = random.choice(watchdogs)
            praise = (f"GOOD NEWS: {wd} reported that {text[:-1]} — residents are grateful.")
            wide = random.sample(all_personas, min(_PRAISE_AUDIENCE, len(all_personas)))
            for tp in wide:
                _add_memory(tp, praise, curr_time, poignancy=8,
                            s=name, p="was credited for", o="good governance",
                            kw={"governance", "praise", "election", name})
            welfare_delta += 0.005
            corruption_delta -= 0.005

    if events:
        print(f"[GOVERNANCE] {events} good act(s), {amplified} amplified; "
              f"welfare +{welfare_delta:.3f}, corruption {corruption_delta:.3f}", flush=True)
    return events, amplified, welfare_delta, corruption_delta
