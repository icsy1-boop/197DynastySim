"""
barangay_survey.py — journalist-run pre-election opinion polls.

In the run-up to the election, journalist agents "go around interviewing
residents" about who they intend to vote for. Concretely: a journalist samples
a set of eligible voters and polls each one's intention via the same memory-based
LLM vote used on election day (so the poll reflects what agents actually know /
feel about the candidates). Results are aggregated into a published survey that
is broadcast as memories (and queued for the news bulletin), which then informs
other voters — enabling bandwagon / strategic shifts in the real election.

This closes another voting feedback path: corruption/protest memories -> voter
intention -> published survey -> more voters informed -> election outcome.

Templated result text (no extra LLM generation beyond the per-respondent poll);
one embedding per injected memory.
"""
import os, random, datetime, logging
from collections import Counter

logger = logging.getLogger(__name__)

# Headline races to poll (barangay-level captain is the main one; mayor too if
# contested). Env-overridable comma list.
SURVEY_POSITIONS = [p.strip() for p in os.environ.get(
    "SURVEY_POSITIONS", "barangay_captain,mayor").split(",") if p.strip()]

_SAMPLE   = int(os.environ.get("SURVEY_SAMPLE", 30))    # residents interviewed
_AUDIENCE = int(os.environ.get("SURVEY_AUDIENCE", 300)) # who hears the published poll


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
        logger.warning(f"[SURVEY] memory inject failed for "
                       f"{getattr(persona.scratch, 'name', '?')}: {e}")


def _is_journalist(name, persona, rows):
    role = str(getattr(persona.scratch, "role", rows.get(name, {}).get("role", "")))
    return "journalist" in role.lower()


def conduct_survey(personas, agent_rows, declared_candidates, curr_time):
    """
    Run one journalist opinion poll. Returns the published survey text (for the
    news bulletin), or None if there are no journalists / not enough candidates.
    """
    from barangay_election import (finalize_candidacy, _vote_for_position,
                                   _POSITION_LABELS, MIN_VOTING_AGE, NON_VOTER_ROLES)

    rows = {r["name"].strip(): r for r in agent_rows}
    journalists = [n for n, p in personas.items() if _is_journalist(n, p, rows)]
    if not journalists:
        return None

    candidates = finalize_candidacy(declared_candidates or {})
    positions = [pos for pos in SURVEY_POSITIONS if len(candidates.get(pos, [])) >= 2]
    if not positions:
        return None

    # Eligible respondents (same rule as the real vote).
    eligible = []
    for n, p in personas.items():
        row = rows.get(n, {})
        role = getattr(p.scratch, "role", row.get("role", ""))
        try:
            age = int(float(row.get("age", 0) or 0))
        except (TypeError, ValueError):
            age = 0
        if age >= MIN_VOTING_AGE and role not in NON_VOTER_ROLES:
            eligible.append((n, p))
    if not eligible:
        return None
    sample = random.sample(eligible, min(_SAMPLE, len(eligible)))

    jname = random.choice(journalists)

    # Flavor: journalists are visibly out interviewing today.
    for jn in journalists:
        try:
            personas[jn].scratch.currently = (
                f"{jn} is conducting an election survey, interviewing residents "
                f"around the barangay about who they intend to vote for.")
        except Exception:
            pass
    _add_memory(personas[jname],
                f"{jname} spent the day interviewing residents across the barangay "
                f"for an election opinion survey.",
                curr_time, 5, jname, "conducted", "election survey",
                {"election", "survey", "journalism", jname})

    # Poll each respondent for each headline position (memory-based LLM vote).
    lines = []
    total = len(sample)
    for pos in positions:
        cnames = candidates[pos]
        label = _POSITION_LABELS.get(pos, pos)
        tally = Counter()
        for n, p in sample:
            fail = cnames[0]
            try:
                chosen, _ = _vote_for_position(p, cnames, label, curr_time, fail)
            except Exception:
                chosen = fail
            tally[chosen] += 1
        ranked = tally.most_common(3)
        frac = ", ".join(f"{nm} {round(100 * ct / total)}%" for nm, ct in ranked)
        lines.append(f"{label} — {frac}")

    text = (f"Election survey by {jname}: based on interviews with {total} residents, "
            + "; ".join(lines) + ".")

    # Publish: a sample of agents "read/hear" the poll (informs the electorate).
    all_personas = list(personas.values())
    audience = random.sample(all_personas, min(_AUDIENCE, len(all_personas)))
    for tp in audience:
        _add_memory(tp, text, curr_time, poignancy=6,
                    s=jname, p="published election survey", o="results",
                    kw={"election", "survey", "poll"})

    print(f"[SURVEY] {jname} polled {total} residents -> {'; '.join(lines)}",
          flush=True)
    return text
