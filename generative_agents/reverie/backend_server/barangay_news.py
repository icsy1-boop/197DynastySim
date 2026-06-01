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
import datetime, logging, random
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

    edu = int(row.get("education_level", 1))
    sc  = row.get("social_class", "lower").strip().lower()

    if edu >= 4 and sc in ("middle", "upper"):
        return 2
    if edu >= 3 or sc == "upper":
        return 1
    if edu >= 2:
        # 40% chance of basic radio access
        return 1 if random.random() < 0.4 else 0
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

    corruption = world_metrics.get("corruption_index", 0.5)
    welfare    = world_metrics.get("welfare_score", 0.5)
    unrest     = world_metrics.get("unrest", 0.3)

    def describe(val, low, mid, high):
        if val < 0.33: return low
        if val < 0.66: return mid
        return high

    prompt = f"""\
You are a barangay radio announcer. Today is {curr_time.strftime("%B %d, %Y")}.

Current community conditions:
- Corruption level: {describe(corruption, 'low', 'moderate', 'high')} ({corruption:.2f})
- Community welfare: {describe(welfare, 'poor', 'fair', 'good')} ({welfare:.2f})
- Social tension: {describe(unrest, 'calm', 'tense', 'volatile')} ({unrest:.2f})

What community members are talking about:
{snippets_text}

Additional context: {context_notes if context_notes else 'None.'}

Write a 3-4 sentence local radio news bulletin that a barangay resident would hear.
Cover local government, community events, or daily life. Be specific and grounded.
Do not make up names of people — refer to roles and events generally.
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
    rows_by_name = {r["name"].strip(): r for r in agent_rows}

    bulletin = generate_news_bulletin(personas, world_metrics, curr_time, context_notes)
    logger.info(f"[NEWS] Bulletin: {bulletin[:80]}...")

    injected = defaultdict(int)  # access_level -> count

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
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        expiration = curr_time + datetime.timedelta(days=14)
        try:
            emb = get_embedding(text)
        except Exception:
            emb = [0.0] * 768
        embedding_pair = (text, emb)
        persona.a_mem.add_thought(
            curr_time, expiration, s, p, o,
            text, set(keywords), poignancy,
            embedding_pair, []
        )
    except Exception as e:
        logger.warning(f"[NEWS] Memory injection failed for {persona.scratch.name}: {e}")
