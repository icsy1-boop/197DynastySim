"""
barangay_unrest.py — protests as the visible consequence of what agents carry
in memory.

No global unrest threshold and no random crowd: a protest happens when enough
INDIVIDUAL residents are personally aggrieved — their own memory stream holds
enough fresh grievance/corruption mass (barangay_mechanics.agent_memory_masses)
— and those same residents are the crowd. Blame is read out of the population's
memories (which officials actually appear in scandal/grievance nodes), never
assigned to random incumbents. The rally text itself is generated from the
protesters' top grievances (falls back to a template if the LLM is down).

Participants physically march: their current action is overridden so they
converge on the venue, rally for a few steps, then disperse (plan() keeps an
action until its duration elapses; execute() paths them there).
"""
import os, random, datetime, logging

from barangay_roles import OFFICIAL_ROLES
from barangay_mechanics import agent_memory_masses, population_blame, _AGGRIEVED_TH

logger = logging.getLogger(__name__)

# Tunables (env-overridable)
_MIN_CROWD = int(os.environ.get("PROTEST_MIN_CROWD", 15))   # aggrieved needed to spark
_AUDIENCE  = int(os.environ.get("PROTEST_AUDIENCE", 250))   # who hears about it
# Grievance loop gain: scales protest-PARTICIPATION poignancy (lived harm).
# Hearers stay at 5 deliberately — scaling awareness re-opens self-amplification.
_GRIEVANCE_GAIN = float(os.environ.get("GRIEVANCE_GAIN", 1.0))
# Physical rally: cap on how many marchers get the action override (perf guard),
# the venue (must be a real arena in maze.address_tiles; <random> spreads the
# crowd across its tiles), and how long they stay (minutes; 60 = one sim-step).
_VENUE     = os.environ.get("PROTEST_VENUE",
                            "Barangay Mabuhay:Road Network:Central Plaza:<random>")
_CROWD_CAP = int(os.environ.get("PROTEST_CROWD", 60))
_DURATION  = int(os.environ.get("PROTEST_DURATION_MIN", 240))   # ~4 steps


def _add_memory(persona, text, curr_time, poignancy, s, p, o, kw):
    """Inject one memory; SKIP (never zero-vector) if embedding fails."""
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        try:
            emb = get_embedding(text)
        except Exception as e:
            logger.warning(f"[PROTEST] embedding failed, memory skipped: {e}")
            return False
        expiration = curr_time + datetime.timedelta(days=30)
        persona.a_mem.add_thought(curr_time, expiration, s, p, o,
                                  text, set(kw), poignancy, (text, emb), [])
        return True
    except Exception as e:
        logger.warning(f"[PROTEST] memory inject failed for "
                       f"{getattr(persona.scratch, 'name', '?')}: {e}")
        return False


def _protest_text(grievance_snippets, blamed_names):
    """One LLM call (default tier — 27B) turning the crowd's actual grievances
    into the rally's message. Template fallback."""
    blame_str = (" Residents name " + ", ".join(blamed_names) +
                 " among those they hold responsible.") if blamed_names else ""
    fallback = ("Residents are protesting in the barangay over worsening public "
                "services and corruption. Anger at the current officials is rising "
                "and many are calling for change in the next election." + blame_str)
    if not grievance_snippets:
        return fallback
    try:
        from persona.prompt_template.gpt_structure import ChatGPT_request
        snips = "\n".join(f"- {s}" for s in grievance_snippets[:6])
        prompt = (
"Residents of a Philippine barangay are marching to the plaza in protest.\n"
"These are the actual grievances they carry:\n"
f"{snips}\n"
f"{('They blame: ' + ', '.join(blamed_names)) if blamed_names else ''}\n"
"Write 2-3 sentences, third person, describing what the protesters are saying "
"and demanding — grounded ONLY in the grievances above. No preamble.")
        out = ChatGPT_request(prompt, max_tokens=110)
        if out and out != "ChatGPT ERROR" and len(out.strip()) > 30:
            return out.strip() + blame_str
    except Exception as e:
        logger.warning(f"[PROTEST] text LLM failed: {e}")
    return fallback


def step_unrest(personas, agent_rows, world_metrics, curr_time):
    """
    Fire a protest if enough residents are personally aggrieved.
    Returns (n_agents_reached, bulletin_text|None).
    Call on a protest-interval cadence from reverie.
    """
    rows = {r["name"].strip(): r for r in agent_rows}

    # Who is actually angry, by their OWN memories (officials don't march).
    # Grievance mass ONLY — lived harm (victim/protest/anger memories), not
    # knowledge of corruption, which saturates once a scandal hits the media.
    aggrieved = []
    grievance_snips = []
    for n, p in personas.items():
        role = getattr(p.scratch, "role", rows.get(n, {}).get("role", ""))
        if role in OFFICIAL_ROLES:
            continue
        m = agent_memory_masses(p, curr_time)
        if m["grievance"] >= _AGGRIEVED_TH:
            aggrieved.append(n)

    if len(aggrieved) < _MIN_CROWD:
        return 0, None

    # The message comes from the crowd's own strongest grievances.
    try:
        from persona.cognitive_modules.converse import _salient_memories
        for n in random.sample(aggrieved, min(8, len(aggrieved))):
            for s in _salient_memories(personas[n], k=2, window_hours=336):
                grievance_snips.append(s)
    except Exception:
        pass

    # Blame is read out of the population's memories, not sampled at random.
    incumbents = [n for n in personas
                  if getattr(personas[n].scratch, "role",
                             rows.get(n, {}).get("role", "")) in OFFICIAL_ROLES]
    blamed = [n for n, _score in population_blame(personas, incumbents,
                                                  curr_time, top_k=3)]

    text = _protest_text(grievance_snips, blamed)

    # Participants carry the rally as lived experience; a wider audience hears.
    all_names = list(personas.keys())
    hearers = set(random.sample(all_names, min(_AUDIENCE, len(all_names)))) - set(aggrieved)
    reached = 0
    _part_poig = max(1, min(9, round(8 * _GRIEVANCE_GAIN)))
    for n in aggrieved:
        if _add_memory(personas[n], f"I joined the protest at the plaza. {text}",
                       curr_time, poignancy=_part_poig,
                       s=n, p="protested against", o="officials",
                       kw={"protest", "unrest", "election", "grievance"}):
            reached += 1
    # Hearers get 5 (< default aggrieved threshold): hearing of a protest is
    # awareness, not lived harm — one heard protest must not make an agent
    # "aggrieved" or protests self-amplify; repeated exposure still adds up.
    for n in hearers:
        if _add_memory(personas[n], f"Residents held a protest at the plaza. {text}",
                       curr_time, poignancy=5,
                       s="residents", p="protest against", o="officials",
                       kw={"protest", "unrest", "election"}):
            reached += 1

    # Make the protest VISIBLE, not just a memory: override the marchers'
    # current action so they converge on the venue and rally, bypassing their
    # daily plan. plan() keeps an action until its duration elapses, and
    # execute() paths each one to the venue's tiles.
    crowd = aggrieved[:_CROWD_CAP]
    for n in crowd:
        sc = personas[n].scratch
        sc.act_address = _VENUE
        sc.act_description = "rallying at the plaza, protesting corrupt officials"
        sc.act_pronunciatio = "✊"   # raised fist
        sc.act_event = (sc.name, "protest against", "corrupt officials")
        sc.act_start_time = curr_time
        sc.act_duration = _DURATION
        sc.act_path_set = False
        sc.planned_path = []
        # Clear any in-progress chat so the gather isn't blocked by conversation.
        sc.chatting_with = None
        sc.chat = None
        sc.chatting_end_time = None

    print(f"[PROTEST] {len(aggrieved)} personally aggrieved (th={_AGGRIEVED_TH}) "
          f"-> {len(crowd)} march on {_VENUE}; blamed: {', '.join(blamed) or '(none)'}",
          flush=True)
    return reached, text
