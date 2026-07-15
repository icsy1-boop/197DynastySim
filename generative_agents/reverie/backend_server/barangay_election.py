"""
barangay_election.py — per-voter, memory-driven barangay election.

Timeline (relative to ELECTION_STEP):
  -720 steps (1 month): announce_election() — all agents learn about upcoming election,
                         open positions, and eligibility rules
  -72  steps (3 days):  declare_candidacy() — candidates announced, campaign memories
                         injected so agents can discuss candidates before voting
   0   steps:           run_election()      — per-voter LLM voting, role changes,
                         result memories injected into all agents

Open positions (Philippine RA 9164):
  - 1 Barangay Captain (Punong Barangay) — chief executive
  - 7 Barangay Kagawad — village council (legislative)
  Treasurer and Secretary are appointed by the captain, not elected.

Anti-dynasty mode (ANTIDYNASTY=1): after vote counting, if a winner's family_id
already holds an elected seat this election cycle, the seat passes to the next
highest vote-getter from a different family.
"""
import os, random, datetime, logging, math
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ELECTED_POSITIONS = {
    "mayor": 1,
    "vice_mayor": 1,
    "councilor": 8,            # Sangguniang Bayan standard for municipalities
    "barangay_captain": 1,
    "barangay_kagawad": 7,
}

from barangay_roles import OFFICIAL_ROLES

# Roles whose current holders are automatically eligible candidates
INCUMBENT_ELIGIBLE = {
    "barangay_captain", "barangay_kagawad", "barangay_treasurer",
    "barangay_secretary", "councilor", "vice_mayor", "mayor",
    "local_elite_political_patron", "civil_servant_admin",
}

# Non-voters (minors / ineligible)
NON_VOTER_ROLES = {"student"}
MIN_VOTING_AGE = 18

RECENCY_DECAY = 0.995   # per sim-hour (matches scratch.recency_decay default)


# ---------------------------------------------------------------------------
# Phase 0 — Election announcement (1 month / 720 steps before election)
# ---------------------------------------------------------------------------

def announce_election(personas, agent_rows, election_date_str, curr_time):
    """
    Inform every agent about the upcoming barangay election.
    Each agent receives a memory with:
      - what positions are open
      - when the election is
      - who is eligible to vote and run
    This runs 720 steps (1 month) before election day so agents can organically
    discuss candidates and politics in the lead-up period.
    """
    positions_str = (
        "Mayor (1 seat), Vice Mayor (1 seat), "
        "Sangguniang Bayan Councilor (8 seats), "
        "Barangay Captain (1 seat), and Barangay Kagawad (7 seats)"
    )
    announcement = (
        f"The local government elections have been officially announced. "
        f"Election day is {election_date_str}. "
        f"Open positions: {positions_str}. "
        f"All residents 18 years and older are eligible to vote. "
        f"Qualified residents may file for candidacy."
    )

    rows_by_name = {r["name"].strip(): r for r in agent_rows}

    for name, persona in personas.items():
        row = rows_by_name.get(name, {})
        age = int(float(row.get("age", 0)))

        if age < MIN_VOTING_AGE:
            personal = (
                f"The barangay election is coming on {election_date_str}. "
                f"The open positions are: {positions_str}. "
                f"{name} is not yet of voting age but is aware of the election."
            )
            poignancy = 3
        else:
            personal = announcement
            poignancy = 5

        _add_memory(
            persona, personal, curr_time, poignancy=poignancy,
            s=name, p="learned about", o="upcoming barangay election",
            keywords={"election", "barangay", "announcement", election_date_str}
        )

    print(f"[ELECTION] Announced to {len(personas)} agents — "
          f"election on {election_date_str}. Open: {positions_str}.")


# ---------------------------------------------------------------------------
# Ongoing political intention polling (monthly pre-announcement,
#                                      weekly post-announcement)
# ---------------------------------------------------------------------------

def _ask_political_intention(persona, election_date_str, current_position_key, announced):
    """
    Ask one agent about their political intentions.
    - announced=False: general interest ("are you thinking about running?")
    - announced=True:  specific commitment, with option to change mind

    Returns (position_key_or_None, changed: bool, reason: str)
      changed=True means they reversed a prior decision (new_key != current_position_key)
    """
    try:
        from persona.prompt_template.gpt_structure import ChatGPT_safe_generate_response
    except ImportError:
        return current_position_key, False, "no LLM"

    positions_list = "\n".join(
        f"  - {label}" for key, label in _POSITION_LABELS.items() if key != "none"
    )

    if not announced:
        context = (
            f"There is no official election announcement yet, but local government "
            f"elections will happen in the future."
        )
        question = (
            "Given everything that has happened in this community and your own life "
            "experiences, are you considering running for political office someday? "
            "If so, which position interests you most?"
        )
    elif current_position_key:
        current_label = _POSITION_LABELS.get(current_position_key, current_position_key)
        context = (
            f"The barangay election has been announced for {election_date_str}. "
            f"You previously indicated you want to run for {current_label}."
        )
        question = (
            f"Do you still intend to run for {current_label}? "
            f"Or have your experiences since then changed your mind? "
            f"You may stay the course, switch to a different position, or withdraw."
        )
    else:
        context = f"The barangay election has been announced for {election_date_str}."
        question = (
            "Now that the election is officially announced, do you want to run for "
            "any of these positions? Think about what you have witnessed and experienced."
        )

    prompt = f"""\
You are {persona.scratch.name}.
About you: {persona.scratch.get_str_iss()}
Your current situation: {persona.scratch.currently}

{context}

Open positions:
{positions_list}

{question}

Answer in this exact format (two lines only):
RUNNING: YES or NO
POSITION: one of [Mayor, Vice Mayor, Sangguniang Bayan Councilor, Barangay Captain, Barangay Kagawad, NONE]"""

    example_output = "RUNNING: NO\nPOSITION: NONE"
    special_instruction = (
        "Two lines only: 'RUNNING: YES or NO' and "
        "'POSITION: <position name or NONE>'. No other text."
    )

    def validate(resp, prompt=""):
        lines = [l.strip() for l in resp.strip().splitlines() if l.strip()]
        return len(lines) >= 2 and lines[0].startswith("RUNNING:") and lines[1].startswith("POSITION:")

    def clean_up(resp, prompt=""):
        lines = [l.strip() for l in resp.strip().splitlines() if l.strip()]
        running = "NO"
        position_label = "NONE"
        for line in lines:
            if line.upper().startswith("RUNNING:"):
                running = line.split(":", 1)[1].strip().upper()
            elif line.upper().startswith("POSITION:"):
                position_label = line.split(":", 1)[1].strip()
        if running != "YES":
            return None
        for key, label in _POSITION_LABELS.items():
            if label.lower() == position_label.lower():
                return key if key != "none" else None
        return None

    new_key = ChatGPT_safe_generate_response(
        prompt, example_output, special_instruction,
        3, current_position_key, validate, clean_up, False
    )
    changed = new_key != current_position_key
    reason = (
        f"{persona.scratch.name} is running for "
        f"{_POSITION_LABELS.get(new_key, 'office')}."
        if new_key else
        f"{persona.scratch.name} decided not to run for office."
    )
    return new_key, changed, reason


def poll_political_intentions(personas, declared_candidates, agent_rows, curr_time,
                              announced=False, election_date_str="the upcoming election"):
    """
    Poll every eligible adult about their political intentions.

    declared_candidates: dict {name -> position_key} — updated in place and returned.
    announced:           False = pre-announcement general poll;
                         True  = post-announcement specific commitment check.

    Runs in parallel. Injects memories for new declarations and withdrawals.
    Returns updated declared_candidates dict.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows_by_name = {r["name"].strip(): r for r in agent_rows}
    eligible = [
        (name, persona)
        for name, persona in personas.items()
        if int(float(rows_by_name.get(name, {}).get("age", 0))) >= MIN_VOTING_AGE
        and rows_by_name.get(name, {}).get("role", "") not in NON_VOTER_ROLES
    ]

    phase = "post-announcement" if announced else "pre-announcement"
    print(f"[ELECTION] Polling {len(eligible)} agents ({phase})...")

    def poll_one(name_persona):
        name, persona = name_persona
        current = declared_candidates.get(name)
        new_key, changed, reason = _ask_political_intention(
            persona, election_date_str, current, announced
        )
        return name, persona, current, new_key, changed, reason

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(poll_one, np): np for np in eligible}
        for future in as_completed(futures):
            try:
                name, persona, old_key, new_key, changed, reason = future.result()
                if not changed:
                    continue
                # Update the running candidate registry
                if new_key:
                    declared_candidates[name] = new_key
                    _inject_campaign_memory(persona, new_key, curr_time, reason)
                    if old_key and old_key != new_key:
                        print(f"[ELECTION] {name} switched from "
                              f"{old_key} → {new_key}")
                    else:
                        print(f"[ELECTION] {name} declared for {new_key}")
                elif old_key:
                    del declared_candidates[name]
                    _add_memory(
                        persona, f"{name} decided to withdraw from the election.",
                        curr_time, poignancy=5,
                        s=name, p="withdrew from", o="election",
                        keywords={"election", "withdraw", name}
                    )
                    print(f"[ELECTION] {name} withdrew from {old_key}")
            except Exception as e:
                logger.warning(f"[ELECTION] Poll failed for agent: {e}")

    running = sum(1 for k in declared_candidates.values() if k)
    print(f"[ELECTION] Poll complete — {running} candidates declared so far.")
    return declared_candidates


# ---------------------------------------------------------------------------
# Phase 1 — Candidacy finalization (step -72: lock in candidates from registry)
# ---------------------------------------------------------------------------

_POSITION_LABELS = {
    "mayor":             "Mayor",
    "vice_mayor":        "Vice Mayor",
    "councilor":         "Sangguniang Bayan Councilor",
    "barangay_captain":  "Barangay Captain",
    "barangay_kagawad":  "Barangay Kagawad",
    "none":              "NONE",
}

def _ask_candidacy(persona, election_date_str):
    """
    Ask this agent via LLM whether they want to run for office and, if so, which
    position. Returns (position_key_or_None, reason_str).
    """
    try:
        from persona.prompt_template.gpt_structure import ChatGPT_safe_generate_response
    except ImportError:
        return None, "no LLM"

    positions_list = "\n".join(
        f"  - {label}" for key, label in _POSITION_LABELS.items() if key != "none"
    )

    prompt = f"""\
You are {persona.scratch.name}.
About you: {persona.scratch.get_str_iss()}
Your current situation: {persona.scratch.currently}

The local government elections have been announced for {election_date_str}.
The following positions are open for election:
{positions_list}

Thinking about your life, your experiences in this community, your relationships,
and your personal goals — are you considering running for any of these positions?

Answer in this exact format (two lines only):
RUNNING: YES or NO
POSITION: one of [Mayor, Vice Mayor, Sangguniang Bayan Councilor, Barangay Captain, Barangay Kagawad, NONE]"""

    example_output = "RUNNING: NO\nPOSITION: NONE"
    special_instruction = (
        "Answer in exactly two lines: "
        "'RUNNING: YES or NO' and "
        "'POSITION: <position name or NONE>'. No other text."
    )

    valid_positions = set(_POSITION_LABELS.values())

    def validate(resp, prompt=""):
        lines = [l.strip() for l in resp.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            return False
        return (lines[0].startswith("RUNNING:") and lines[1].startswith("POSITION:"))

    def clean_up(resp, prompt=""):
        lines = [l.strip() for l in resp.strip().splitlines() if l.strip()]
        running = "NO"
        position_label = "NONE"
        for line in lines:
            if line.upper().startswith("RUNNING:"):
                running = line.split(":", 1)[1].strip().upper()
            elif line.upper().startswith("POSITION:"):
                position_label = line.split(":", 1)[1].strip()
        if running != "YES":
            return None
        # Map label back to key
        for key, label in _POSITION_LABELS.items():
            if label.lower() == position_label.lower():
                return key if key != "none" else None
        return None

    result = ChatGPT_safe_generate_response(
        prompt, example_output, special_instruction,
        3, None, validate, clean_up, False
    )
    reason = f"{persona.scratch.name} decided {'to run' if result else 'not to run'} for office."
    return result, reason


def finalize_candidacy(declared_candidates):
    """
    Convert the running {name -> position_key} registry into
    {position_key -> [name, ...]} for voting.
    Called at step ELECTION_STEP - 72 to lock in the candidate list.
    """
    candidates = defaultdict(list)
    for name, pos_key in declared_candidates.items():
        if pos_key:
            candidates[pos_key].append(name)
    for pos, names in candidates.items():
        print(f"[ELECTION] Final candidates — "
              f"{_POSITION_LABELS.get(pos, pos)}: {len(names)}")
    return dict(candidates)


def _inject_campaign_memory(persona, position_key, curr_time, reason=None):
    label = _POSITION_LABELS.get(position_key, position_key)
    text = (
        reason if reason and "decided to run" in reason
        else f"{persona.scratch.name} has decided to run for {label} "
             f"in the upcoming election."
    )
    _add_memory(persona, text, curr_time, poignancy=6,
                s=persona.scratch.name, p="is running for", o=label,
                keywords={"election", label, persona.scratch.name})


# ---------------------------------------------------------------------------
# Phase 2 — Per-voter LLM voting
# ---------------------------------------------------------------------------

def _retrieve_candidate_memories(voter, candidate_name, curr_time, max_n=5):
    """
    Return up to max_n memory strings from voter's memory that mention
    candidate_name, ranked by poignancy × recency.
    """
    hits = []
    all_nodes = voter.a_mem.seq_event + voter.a_mem.seq_thought

    for node in all_nodes:
        text = getattr(node, "embedding_key", "")
        if candidate_name.lower() not in text.lower():
            continue
        created = getattr(node, "created", curr_time)
        elapsed_h = max(0, (curr_time - created).total_seconds() / 3600)
        recency = RECENCY_DECAY ** elapsed_h
        poignancy = getattr(node, "poignancy", 1)
        score = poignancy * recency
        hits.append((score, text))

    hits.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in hits[:max_n]]


def _vote_for_position(voter, candidate_names, position, curr_time, fail_safe_name):
    """
    Ask the LLM (via existing ChatGPT_safe_generate_response) who this voter
    votes for. Returns (chosen_name, reason_text).
    """
    try:
        from persona.prompt_template.gpt_structure import ChatGPT_safe_generate_response
    except ImportError:
        logger.warning("[ELECTION] Could not import gpt_structure; using fail-safe vote.")
        return fail_safe_name, "no LLM available"

    # Build memory context per candidate
    mem_sections = []
    for cname in candidate_names:
        mems = _retrieve_candidate_memories(voter, cname, curr_time)
        if mems:
            mem_sections.append(
                f"  {cname}:\n" + "\n".join(f"    - {m}" for m in mems)
            )
        else:
            mem_sections.append(f"  {cname}: (no direct memories)")

    mem_block = "\n".join(mem_sections) if mem_sections else "  (no relevant memories)"

    prompt = f"""\
You are {voter.scratch.name}.
About you: {voter.scratch.get_str_iss()}
Your current situation: {voter.scratch.currently}

The barangay election is being held today. You are voting for {position}.

Candidates:
{chr(10).join(f'  - {c}' for c in candidate_names)}

Your memories and reflections about these candidates:
{mem_block}

Based on your personal experiences, interactions, family ties, and reflections,
who do you vote for as {position}?

Reply with ONLY the full name of your chosen candidate — no explanation.
If you truly have no basis or faith in any of these candidates, you may reply ABSTAIN."""

    example_output = candidate_names[0]
    special_instruction = (
        f"Reply with ONLY the exact full name of one candidate from this list: "
        f"{', '.join(candidate_names)} — or the single word ABSTAIN. "
        f"Do not add any other text."
    )

    valid_names_lower = {c.lower() for c in candidate_names}

    def validate(resp, prompt=""):
        r = resp.strip().lower()
        return r in valid_names_lower or r == "abstain"

    def clean_up(resp, prompt=""):
        resp = resp.strip()
        if resp.lower() == "abstain":
            return "ABSTAIN"
        # Match case-insensitively back to the original name
        for c in candidate_names:
            if c.lower() == resp.lower():
                return c
        return fail_safe_name

    result = ChatGPT_safe_generate_response(
        prompt, example_output, special_instruction,
        3, fail_safe_name, validate, clean_up, False
    )
    chosen = result if result else fail_safe_name

    if chosen == "ABSTAIN":
        return chosen, f"{voter.scratch.name} chose not to vote for {position}."

    # Build reason for memory
    mems = _retrieve_candidate_memories(voter, chosen, curr_time, max_n=2)
    reason = mems[0] if mems else f"{voter.scratch.name} voted based on personal judgment."

    return chosen, reason


_VOTE_WORKERS = int(os.environ.get("ELECTION_VOTE_WORKERS", 24))


def collect_votes(personas, candidates, agent_rows, curr_time):
    """
    Each eligible voter casts a vote for each position via LLM (voters run in
    parallel — serially this was ~2000 calls in a Python loop). ABSTAIN is a
    valid emergent outcome. On LLM failure the fail-safe is memory-derived:
    family candidate first, else the candidate this voter's own memories trust
    most (barangay_mechanics.name_trust), else a random candidate — never
    "first name in the list".
    Returns dict {position -> Counter({candidate_name: vote_count})}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from barangay_mechanics import name_trust

    rows_by_name = {r["name"].strip(): r for r in agent_rows}
    vote_counts = {pos: Counter() for pos in candidates}
    vote_memories = []   # (voter_name, position, chosen, reason)
    n_abstain = 0

    all_candidate_names = sorted({c for cl in candidates.values() for c in cl})

    voters = []
    for name, persona in personas.items():
        row = rows_by_name.get(name, {})
        role = getattr(persona.scratch, "role", row.get("role", ""))
        age = int(float(row.get("age", 0)))
        if age >= MIN_VOTING_AGE and role not in NON_VOTER_ROLES:
            voters.append((name, persona))

    def vote_one(name, persona):
        row = rows_by_name.get(name, {})
        trust = name_trust(persona, all_candidate_names, curr_time)
        results = []
        for position, cnames in candidates.items():
            if not cnames:
                continue
            # Family loyalty: family member in candidate list → strong pull
            voter_fam = row.get("family_id", "")
            family_candidates = [
                c for c in cnames
                if rows_by_name.get(c, {}).get("family_id") == voter_fam and c != name
            ]
            if family_candidates:
                fail_safe = family_candidates[0]
            else:
                scored = sorted(((trust.get(c, 0.0), c) for c in cnames),
                                reverse=True)
                fail_safe = scored[0][1] if scored[0][0] > 0 else random.choice(cnames)

            chosen, reason = _vote_for_position(
                persona, cnames, position, curr_time, fail_safe
            )
            results.append((position, chosen, reason))
        return name, results

    with ThreadPoolExecutor(max_workers=_VOTE_WORKERS) as executor:
        futures = {executor.submit(vote_one, n, p): n for n, p in voters}
        for future in as_completed(futures):
            try:
                name, results = future.result()
            except Exception as e:
                logger.warning(f"[ELECTION] vote failed for {futures[future]}: {e}")
                continue
            for position, chosen, reason in results:
                if chosen == "ABSTAIN":
                    n_abstain += 1
                    continue
                vote_counts[position][chosen] += 1
                vote_memories.append((name, position, chosen, reason))

    if n_abstain:
        print(f"[ELECTION] {n_abstain} position-votes were abstentions")

    # Inject voting memories
    for voter_name, position, chosen, reason in vote_memories:
        if voter_name in personas:
            text = f"{voter_name} voted for {chosen} as {position}. {reason}"
            _add_memory(
                personas[voter_name], text, curr_time, poignancy=4,
                s=voter_name, p="voted for", o=chosen,
                keywords={"election", "vote", chosen, position}
            )

    return vote_counts


# ---------------------------------------------------------------------------
# Phase 3 — Resolve winners, apply roles, inject result memories
# ---------------------------------------------------------------------------

def resolve_winners(vote_counts, candidates, personas, agent_rows, antidynasty):
    """
    Convert vote counts to winner assignments.
    With antidynasty=True, a candidate is skipped if their family already holds
    a seat elected in this cycle.
    Returns dict {position -> [winner_name, ...]}
    """
    rows_by_name = {r["name"].strip(): r for r in agent_rows}
    winners = {}
    elected_families = set()

    for position, n_seats in ELECTED_POSITIONS.items():
        ranking = vote_counts.get(position, Counter()).most_common()
        seats = []

        for candidate_name, votes in ranking:
            if len(seats) >= n_seats:
                break
            fam = rows_by_name.get(candidate_name, {}).get("family_id", "")
            if antidynasty and fam and fam in elected_families:
                logger.info(f"[ELECTION] Anti-dynasty: {candidate_name} blocked "
                            f"({fam} already has elected member)")
                continue
            seats.append(candidate_name)
            if fam:
                elected_families.add(fam)

        winners[position] = seats

    return winners


def apply_role_changes(winners, personas, agent_rows):
    """
    Promote winners and demote outgoing officials. Routes through persona_md so
    the change updates not just role/tier but the identity fields that drive the
    daily plan (lifestyle / currently / duties) AND writes it back to the agent's
    .md — so a demoted official actually stops reporting to Barangay Hall and a
    new winner takes up their office.
    """
    import persona_md
    rows_by_name = {r["name"].strip(): r for r in agent_rows}
    winner_names = {n for seats in winners.values() for n in seats}

    # Demote current officials who didn't win
    for name, persona in personas.items():
        role = getattr(persona.scratch, "role", "")
        if role in ELECTED_POSITIONS and name not in winner_names:
            persona_md.apply_role(persona, rows_by_name.get(name), "civil_servant_admin")
            persona_md.write_md(persona, rows_by_name.get(name))
            logger.info(f"[ELECTION] {name} lost office → civil_servant_admin")

    # Promote winners
    for position, seat_list in winners.items():
        for winner_name in seat_list:
            if winner_name in personas:
                persona_md.apply_role(personas[winner_name],
                                      rows_by_name.get(winner_name), position)
                persona_md.write_md(personas[winner_name],
                                    rows_by_name.get(winner_name))
                logger.info(f"[ELECTION] {winner_name} → {position}")


def inject_result_memories(winners, personas, agent_rows, vote_counts, curr_time):
    """
    Give every agent a memory of the election results.
    """
    rows_by_name = {r["name"].strip(): r for r in agent_rows}
    winner_names = {n for seats in winners.values() for n in seats}

    captain_list = winners.get("barangay_captain", [])
    kagawad_list = winners.get("barangay_kagawad", [])

    captain_str = captain_list[0] if captain_list else "unknown"
    kagawad_str = ", ".join(kagawad_list) if kagawad_list else "unknown"

    headline = (
        f"The barangay election results are in. "
        f"{captain_str} was elected as barangay captain. "
        f"The new kagawad are: {kagawad_str}."
    )

    for name, persona in personas.items():
        fam = rows_by_name.get(name, {}).get("family_id", "")
        family_won = any(
            rows_by_name.get(w, {}).get("family_id") == fam
            for w in winner_names if fam
        )

        if name in winner_names:
            personal = f"{name} won the barangay election and now holds office. {headline}"
            poignancy = 9
        elif family_won:
            personal = f"A member of the {fam} family won the election. {headline}"
            poignancy = 7
        else:
            personal = headline
            poignancy = 5

        _add_memory(
            persona, personal, curr_time, poignancy=poignancy,
            s=name, p="learned about", o="election results",
            keywords={"election", "barangay", captain_str}
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_election(personas, agent_rows, antidynasty=False, curr_time=None,
                 candidates=None):
    """
    Full election pipeline:
      1. Use pre-built candidates dict (from finalize_candidacy) or fall back
         to asking all agents if none supplied
      2. Collect per-voter LLM votes
      3. Resolve winners (with optional anti-dynasty constraint)
      4. Apply role changes
      5. Inject result memories
    Returns dict {position -> [winner_name, ...]}
    """
    if curr_time is None:
        curr_time = datetime.datetime.now()

    if not candidates:
        print(f"[ELECTION] No pre-built candidate list — running emergency poll")
        declared = poll_political_intentions(
            personas, {}, agent_rows, curr_time,
            announced=True, election_date_str=curr_time.strftime("%B %d, %Y"))
        candidates = finalize_candidacy(declared)

    print(f"[ELECTION] Phase 2: collecting votes ({len(personas)} agents)")
    vote_counts = collect_votes(personas, candidates, agent_rows, curr_time)

    for pos, counts in vote_counts.items():
        top = counts.most_common(3)
        print(f"[ELECTION] {pos} top votes: {top}")

    print(f"[ELECTION] Phase 3: resolving winners (antidynasty={antidynasty})")
    winners = resolve_winners(vote_counts, candidates, personas, agent_rows, antidynasty)

    apply_role_changes(winners, personas, agent_rows)
    inject_result_memories(winners, personas, agent_rows, vote_counts, curr_time)

    print(f"[ELECTION] Done. Winners: { {p: v for p, v in winners.items()} }")
    return winners


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
            logger.warning(f"[ELECTION] embedding failed, memory skipped: {e}")
            return False
        expiration = curr_time + datetime.timedelta(days=30)
        persona.a_mem.add_thought(
            curr_time, expiration, s, p, o,
            text, set(keywords), poignancy,
            (text, emb), []
        )
        return True
    except Exception as e:
        logger.warning(f"[ELECTION] Memory injection failed for {persona.scratch.name}: {e}")
        return False
