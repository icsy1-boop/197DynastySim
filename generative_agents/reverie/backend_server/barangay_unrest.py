"""
barangay_unrest.py — protests as the visible consequence of the welfare/unrest loop.

When the integrated `unrest` world metric crosses a threshold (driven by sustained
corruption + low welfare), residents protest: a high-poignancy "residents are
protesting corruption and poor services" memory is injected into a wide sample of
agents, and the event text is queued for the next news bulletin. Those memories
then surface in the memory-based election voting as anti-incumbent sentiment, so
corruption -> welfare down -> unrest up -> protest -> votes is closed end to end.

Templated text only (no LLM generation); one embedding per injected memory.
"""
import os, random, datetime, logging

logger = logging.getLogger(__name__)

OFFICIAL_ROLES = {
    "mayor", "vice_mayor", "councilor",
    "barangay_captain", "barangay_kagawad",
}

# Tunables (env-overridable)
_THRESHOLD = float(os.environ.get("UNREST_PROTEST_THRESHOLD", 0.60))
_AUDIENCE  = int(os.environ.get("PROTEST_AUDIENCE", 250))
# Physical rally: how many aggrieved residents actually march to the venue, the
# venue address (must be a real arena in maze.address_tiles; <random> spreads the
# crowd across its tiles), and how long they stay (minutes; 60 = one sim-step).
_VENUE     = os.environ.get("PROTEST_VENUE",
                            "Barangay Mabuhay:Road Network:Central Plaza:<random>")
_CROWD     = int(os.environ.get("PROTEST_CROWD", 60))
_DURATION  = int(os.environ.get("PROTEST_DURATION_MIN", 240))   # ~4 steps


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
        logger.warning(f"[PROTEST] memory inject failed for "
                       f"{getattr(persona.scratch, 'name', '?')}: {e}")


def step_unrest(personas, agent_rows, world_metrics, curr_time):
    """
    Fire a protest if unrest is high. Returns (n_agents_reached, bulletin_text|None).
    Call on a protest-interval cadence from reverie.
    """
    unrest  = float(world_metrics.get("unrest", 0.0))
    welfare = float(world_metrics.get("welfare_score", 0.5))
    if unrest < _THRESHOLD:
        return 0, None

    rows = {r["name"].strip(): r for r in agent_rows}
    incumbents = [n for n in personas
                  if rows.get(n, {}).get("role", "") in OFFICIAL_ROLES]
    blame = ""
    if incumbents:
        blame = (" Residents named "
                 + ", ".join(random.sample(incumbents, min(3, len(incumbents))))
                 + " among those they hold responsible.")

    text = ("Residents are protesting in the barangay over worsening public "
            "services and corruption. Anger at the current officials is rising "
            "and many are calling for change in the next election." + blame)

    all_personas = list(personas.values())
    sample = random.sample(all_personas, min(_AUDIENCE, len(all_personas)))
    for tp in sample:
        _add_memory(tp, text, curr_time, poignancy=8,
                    s="residents", p="protest against", o="officials",
                    kw={"protest", "unrest", "corruption", "election", "officials"})

    # Make the protest VISIBLE, not just a memory: override a crowd of aggrieved
    # residents' current action so they march to the venue and rally for a few
    # steps, bypassing their daily plan. plan() keeps an action until its
    # duration elapses, and execute() paths each one to the venue's tiles — so
    # they physically converge on the plaza, then disperse when the rally ends.
    crowd_pool = [tp for tp in sample
                  if rows.get(tp.scratch.name, {}).get("role", "") not in OFFICIAL_ROLES]
    crowd = random.sample(crowd_pool, min(_CROWD, len(crowd_pool)))
    for p in crowd:
        sc = p.scratch
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

    print(f"[PROTEST] unrest={unrest:.2f} welfare={welfare:.2f} "
          f"-> {len(sample)} agents hear; {len(crowd)} march on {_VENUE}", flush=True)
    return len(sample), text
