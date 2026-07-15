"""
barangay_news.py — media broadcast and information spread.

Weekly news bulletins are generated via one LLM call and injected into
agents who have media access (TV, radio, newspaper, smartphone).
Information then spreads organically through the existing conversation
system — no special spread mechanic needed.

Media access levels (derived from role/education/social_class):
  3 — Journalist / media professional: generates AND distributes news
  2 — Educated / upper-middle class: TV, newspaper, internet
  1 — Basic access: radio, community bulletin board
  0 — No regular access: relies entirely on word of mouth
"""
import os, datetime, logging, random
from collections import defaultdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Media access determination
# ---------------------------------------------------------------------------

# Roles with guaranteed access
_ROLE_ACCESS = {
    "local_journalist":        3,
    "mayor":                   2,
    "vice_mayor":              2,
    "councilor":               2,
    "barangay_captain":        2,
    "barangay_kagawad":        2,
    "barangay_secretary":      2,
    "municipal_engineer":      2,
    "municipal_budget_officer":2,
    "procurement_officer":     2,
    "coa_auditor":             2,
    "teacher":                 2,
    "doctor":                  2,
    "nurse":                   2,
    "lawyer":                  2,
    "contractor_owner":        2,
    "business_owner":          2,
    "private_sector_manager":  2,
    "cso_organizer":           2,
    "local_elite_political_patron": 2,
    "civil_servant_admin":     1,
    "clerk_office_worker":     1,
    "police_officer":          1,
    "social_welfare_officer":  1,
    "disaster_officer":        1,
    "sari_sari_store_owner":   1,
    "market_stall_owner":      1,
}

def media_access_level(row):
    """Return 0-3 access level for an agent row."""
    role = row.get("role", "").strip()
    if role in _ROLE_ACCESS:
        return _ROLE_ACCESS[role]

    try:
        edu = int(row.get("education_level", 1))
    except (TypeError, ValueError):
        edu = 1
    sc  = (row.get("social_class", "lower") or "lower").strip().lower()

    # Deterministic (no RNG): the control and anti-dynasty arms must not
    # differ in who hears the news by coin flip.
    if edu >= 4 and sc in ("middle", "upper"):
        return 2
    if edu >= 2 or sc == "upper":
        return 1
    return 0


# ---------------------------------------------------------------------------
# News bulletin generation
# ---------------------------------------------------------------------------

def _sample_community_thoughts(personas, n=8):
    """
    Sample recent thought nodes across all agents to give the LLM a sense
    of what is on the community's mind. Returns a list of text snippets.
    """
    all_thoughts = []
    for persona in personas.values():
        nodes = getattr(persona.a_mem, "seq_thought", [])
        if nodes:
            # Take the most recent thought from each persona
            all_thoughts.append(nodes[-1].embedding_key)

    random.shuffle(all_thoughts)
    return all_thoughts[:n]


def generate_news_bulletin(personas, world_metrics, curr_time, context_notes=""):
    """
    Generate a radio/TV news bulletin via one LLM call.

    world_metrics : dict with optional keys: corruption_index (0-1),
                    welfare_score (0-1), unrest (0-1), recent_events (list[str])
    context_notes : any extra context (election upcoming, budget period, etc.)

    Returns the bulletin text, or a template fallback if LLM is unavailable.
    """
    try:
        from persona.prompt_template.gpt_structure import ChatGPT_safe_generate_response
    except ImportError:
        return _template_bulletin(world_metrics, curr_time, context_notes)

    community_snippets = _sample_community_thoughts(personas)
    snippets_text = "\n".join(f"  - {s}" for s in community_snippets) or "  (no data)"

    recent_events = world_metrics.get("recent_events") or []
    events_text = ("\n".join(f"  - {e}" for e in recent_events[-3:])
                   if recent_events else "  (none)")

    # The bulletin is written from what the JOURNALIST actually carries in
    # memory (what they witnessed, exposed, heard), not from the world-metric
    # numbers — otherwise the metric feeds the narrative that feeds the metric.
    journalist_mems = []
    journalist_name = None
    for name, p in personas.items():
        if "journalist" in str(getattr(p.scratch, "role", "")).lower() or \
           "journalist" in str(getattr(p.scratch, "learned", "")).lower():
            journalist_name = name
            try:
                from persona.cognitive_modules.converse import _salient_memories
                journalist_mems = _salient_memories(p, k=6, window_hours=336)
            except Exception:
                journalist_mems = []
            break
    mems_text = ("\n".join(f"  - {m}" for m in journalist_mems)
                 if journalist_mems else "  (a quiet week — nothing major witnessed)")

    prompt = f"""\
You are {journalist_name or 'the local journalist'}, preparing the barangay radio news bulletin. Today is {curr_time.strftime("%B %d, %Y")}.

What you, the journalist, have personally witnessed, verified, or been told recently:
{mems_text}

Stories already published / notable recent events:
{events_text}

What community members are talking about:
{snippets_text}

Additional context: {context_notes if context_notes else 'None.'}

Write a 3-4 sentence local radio news bulletin that a barangay resident would hear,
grounded ONLY in the material above. Cover local government, community events, or
daily life. You may name officials that appear in your material; do not invent names.
Output only the bulletin text, nothing else."""

    example = (
        "Good morning, Barangay residents. Local officials met yesterday to discuss "
        "the upcoming budget deliberations amid growing concerns about public funds. "
        "Community leaders urge residents to stay informed and report irregularities."
    )
    special = "Output only the news bulletin text, 3-4 sentences, no headers or labels."

    def validate(resp, prompt=""): return len(resp.strip()) > 30
    def clean_up(resp, prompt=""): return resp.strip()

    result = ChatGPT_safe_generate_response(
        prompt, example, special, 2,
        _template_bulletin(world_metrics, curr_time, context_notes),
        validate, clean_up, False
    )
    return result if result else _template_bulletin(world_metrics, curr_time, context_notes)


def _template_bulletin(world_metrics, curr_time, context_notes=""):
    date_str = curr_time.strftime("%B %d, %Y")
    corruption = world_metrics.get("corruption_index", 0.5)
    welfare    = world_metrics.get("welfare_score", 0.5)

    tone = ("under scrutiny for alleged irregularities" if corruption > 0.6
            else "carrying out normal operations")
    welfare_desc = ("struggling" if welfare < 0.4
                    else "stable" if welfare < 0.7 else "improving")

    bulletin = (
        f"This is your barangay update for {date_str}. "
        f"Local government offices are {tone}. "
        f"Community welfare conditions remain {welfare_desc}. "
    )
    if context_notes:
        bulletin += context_notes
    return bulletin.strip()


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

def broadcast_news(personas, agent_rows, world_metrics, curr_time,
                   context_notes=""):
    """
    Generate a news bulletin and inject it into agents based on their
    media access level. Higher-access agents receive it with higher poignancy
    and are more likely to re-share it in conversations.

    Journalists (level 3) receive a special "source" memory that marks them
    as primary information nodes — they are most likely to bring it up.

    Returns the bulletin text.
    """
    from barangay_mechanics import agent_memory_masses

    rows_by_name = {r["name"].strip(): r for r in agent_rows}

    bulletin = generate_news_bulletin(personas, world_metrics, curr_time, context_notes)
    logger.info(f"[NEWS] Bulletin: {bulletin[:80]}...")

    injected = defaultdict(int)  # access_level -> count
    relevance_mass = float(os.environ.get("NEWS_RELEVANCE_MASS", 4.0))

    for name, persona in personas.items():
        row = rows_by_name.get(name, {})
        level = media_access_level(row)
        if level == 0:
            continue  # no access — hears through conversations only

        if level == 3:
            # Journalists: source-level memory, high poignancy, framed as their job
            text = (
                f"{name} reported on the following news as part of their work: "
                f"{bulletin}"
            )
            poignancy = 8
        elif level == 2:
            text = (
                f"{name} watched the news on TV and learned: {bulletin}"
            )
            poignancy = 6
        else:
            text = (
                f"{name} heard on the radio: {bulletin}"
            )
            poignancy = 4

        # Personal relevance: news lands harder on someone already carrying
        # grievance/corruption memories — it confirms what they lived through.
        try:
            m = agent_memory_masses(persona, curr_time)
            if (m["grievance"] + m["corruption"]) >= relevance_mass:
                poignancy = min(9, poignancy + 2)
        except Exception:
            pass

        _add_memory(persona, text, curr_time, poignancy=poignancy,
                    s=name, p="heard news about", o="local government",
                    keywords={"news", "barangay", "broadcast"})
        injected[level] += 1

    total = sum(injected.values())
    print(f"[NEWS] Broadcast complete — {total} agents informed "
          f"(journalists: {injected[3]}, TV/paper: {injected[2]}, "
          f"radio: {injected[1]}). "
          f"Remaining {len(personas) - total} agents rely on word-of-mouth.")
    return bulletin


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _add_memory(persona, text, curr_time, poignancy, s, p, o, keywords):
    """Inject one memory; SKIP (never zero-vector) if embedding fails — a zero
    vector would poison cosine retrieval for every later query."""
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        try:
            emb = get_embedding(text)
        except Exception as e:
            logger.warning(f"[NEWS] embedding failed, memory skipped: {e}")
            return False
        expiration = curr_time + datetime.timedelta(days=14)
        persona.a_mem.add_thought(
            curr_time, expiration, s, p, o,
            text, set(keywords), poignancy,
            (text, emb), []
        )
        return True
    except Exception as e:
        logger.warning(f"[NEWS] Memory injection failed for {persona.scratch.name}: {e}")
        return False
